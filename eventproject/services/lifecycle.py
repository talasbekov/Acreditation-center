"""Этап C — единый жизненный цикл участника и заявки.

Решения владельца (24.11.2026):
- допуск выдаётся каждому участнику отдельно;
- проверяет супероператор (или суперпользователь);
- «Отправить» заявку отправляет на проверку всех её участников-черновиков и
  закрывает им правку до решения проверяющего.

Цикл участника: draft → submitted → in_review → ready → exported, возврат
in_review → draft с обязательной причиной. Все интерфейсы (HTML RU/KZ/EN, API,
очередь проверки) вызывают переходы только отсюда: проверка допустимости,
блокировка строки, аудит и пересчёт статуса заявки выполняются в одном месте.

Статус заявки (`Request.status`) остаётся для прежних экранов и сверочных JSON:
Active — оператор может править; Checking — предпросмотр; Sent — отправлена.
Возврат хотя бы одного участника переводит отправленную заявку обратно в Active,
чтобы оператор увидел и исправил возвращённую карточку.
"""

from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from eventproject.audit import audit_log
from eventproject.models import Attendee, Request
from eventproject.state_machine import AttendeeStatus, InvalidStatusTransition, assert_transition
from eventproject.validators.residency import resolve_residency

REQUEST_EDITABLE = {"Active", "Checking"}
REQUEST_SENT = "Sent"
REQUEST_ACTIVE = "Active"
# Прежний режим предпросмотра. Новый код его не ставит: предпросмотр — только
# чтение. Заявки, оставшиеся в Checking от старой версии, работают как Active.
REQUEST_LEGACY_PREVIEW = "Checking"

# Правка и удаление: оператору — только черновик; никому — после одобрения.
OPERATOR_EDITABLE = {AttendeeStatus.DRAFT}
LOCKED_FOR_EVERYONE = {AttendeeStatus.READY, AttendeeStatus.EXPORTED}

RETURN_REASON_MAX = 1000


class LifecycleError(Exception):
    """Переход невозможен. `problems` — {attendee_id: [что не так]} для отправки заявки."""

    def __init__(self, message, *, problems=None, conflict=True, code=None):
        super().__init__(message)
        self.message = message
        self.problems = problems or {}
        self.conflict = conflict
        self.code = code


@dataclass
class SubmitResult:
    submitted: list = field(default_factory=list)
    already_sent: bool = False


def is_reviewer(user):
    return bool(user and user.is_authenticated and user.role in ("superoperator", "superuser"))


def can_modify(user, attendee):
    """Можно ли этому пользователю править или удалить участника в текущем статусе."""
    if attendee.status in LOCKED_FOR_EVERYONE:
        return False
    if is_reviewer(user):
        return True
    return attendee.status in OPERATOR_EDITABLE


def can_add_to(request_obj):
    return request_obj.status in REQUEST_EDITABLE


def can_preview(request_obj):
    """Предпросмотр и кнопка «Отправить» — пока заявка открыта для правки."""
    return request_obj.status in REQUEST_EDITABLE


def leave_legacy_preview(request_obj):
    """«Вернуться к редактированию»: снять прежний статус Checking.

    Отправленную заявку не трогает — раньше этот POST переводил в Active и её.
    """
    if request_obj.status == REQUEST_LEGACY_PREVIEW:
        request_obj.status = REQUEST_ACTIVE
        request_obj.save(update_fields=["status"])
    return request_obj


def submission_problems(attendee):
    """Коды того, чего не хватает участнику для отправки (пустой список — готов)."""
    problems = []
    residency = resolve_residency(attendee.countryId, attendee.iin, attendee.birthDate)
    if residency.error:
        problems.append("iin")
    if not (attendee.photo and attendee.photo.name):
        problems.append("photo")
    if not (attendee.docScan and attendee.docScan.name):
        problems.append("doc_scan")
    return problems


# Тексты для HTML на трёх языках. Казахский перевод требует проверки носителем.
_TEXT = {
    "ru": {
        "not_ready": "Заявка не отправлена: не все участники готовы.",
        "empty": "Заявка не отправлена: в ней нет участников.",
        "iin": "ИИН не заполнен или неверен",
        "photo": "нет фото",
        "doc_scan": "нет скана документа",
        "locked": "Участник уже отправлен на проверку или допущен — изменить его нельзя.",
        "closed": "Заявка отправлена — добавить участника нельзя.",
    },
    "kz": {
        "not_ready": "Өтінім жіберілмеді: барлық қатысушы дайын емес.",
        "empty": "Өтінім жіберілмеді: онда қатысушылар жоқ.",
        "iin": "ЖСН толтырылмаған немесе қате",
        "photo": "фото жоқ",
        "doc_scan": "құжат көшірмесі жоқ",
        "locked": "Қатысушы тексеруге жіберілген немесе рұқсат алған — оны өзгертуге болмайды.",
        "closed": "Өтінім жіберілген — қатысушы қосуға болмайды.",
    },
    "en": {
        "not_ready": "The application was not sent: not all attendees are ready.",
        "empty": "The application was not sent: it has no attendees.",
        "iin": "IIN missing or invalid",
        "photo": "no photo",
        "doc_scan": "no document scan",
        "locked": "The attendee is already under review or approved and cannot be changed.",
        "closed": "The application has been sent; attendees cannot be added.",
    },
}


def text(key, lang="ru"):
    return _TEXT.get(lang, _TEXT["ru"])[key]


def local_time(value):
    """Момент для экрана оператора: местное время проекта, «24.11.2026 17:47»."""
    if value is None:
        return ""
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    return value.strftime("%d.%m.%Y %H:%M")


def lifecycle_message(exc, lang="ru"):
    """Сообщение об отказе для HTML: общая фраза и список карточек с проблемами."""
    if not exc.problems:
        return text(exc.code, lang) if exc.code else exc.message
    names = {
        a.pk: " ".join(p for p in (a.surname, a.firstname) if p) or f"#{a.pk}"
        for a in Attendee.objects.filter(pk__in=exc.problems)
    }
    lines = [
        f"{names.get(pk, f'#{pk}')}: {', '.join(text(code, lang) for code in codes)}"
        for pk, codes in sorted(exc.problems.items())
    ]
    return text("not_ready", lang) + " " + "; ".join(lines)


def _audit_transition(user, ip, attendee, old, new, extra=None):
    audit_log(
        user=user,
        action="attendee.status_change",
        obj_type="Attendee",
        obj_id=str(attendee.pk),
        ip=ip or "",
        extra={"from": old, "to": new, **(extra or {})},
    )


def _locked_attendee(attendee_id):
    return Attendee.objects.select_for_update().select_related("request").get(pk=attendee_id)


def _move(attendee, target):
    try:
        assert_transition(attendee.status, target)
    except InvalidStatusTransition as exc:
        raise LifecycleError(str(exc)) from exc


def submit_attendee(attendee_id, user, ip=None):
    """draft → submitted для одного участника (API). Повтор для уже отправленного — без изменений."""
    with transaction.atomic():
        attendee = _locked_attendee(attendee_id)
        if attendee.status == AttendeeStatus.SUBMITTED:
            return attendee
        _move(attendee, AttendeeStatus.SUBMITTED)
        problems = submission_problems(attendee)
        if problems:
            raise LifecycleError("Участник не готов к отправке", problems={attendee.pk: problems}, conflict=False)
        old = attendee.status
        attendee.status = AttendeeStatus.SUBMITTED
        attendee.review_comment = ""
        attendee.save(update_fields=["status", "review_comment"])
        _audit_transition(user, ip, attendee, old, attendee.status)
        return attendee


def submit_request(request_id, user, ip=None):
    """Отправить заявку: все её черновики → submitted, заявка → Sent.

    Всё или ничего: если хотя бы у одного черновика не хватает данных, ни один
    участник не меняет статус, а в ошибке перечислены проблемные карточки.
    Повторная отправка без новых черновиков ничего не меняет и возвращает
    `already_sent=True`.
    """
    with transaction.atomic():
        req = Request.objects.select_for_update().get(pk=request_id)
        attendees = list(Attendee.objects.select_for_update().filter(request=req).order_by("id"))
        if not attendees:
            raise LifecycleError("В заявке нет участников", conflict=False, code="empty")

        drafts = [a for a in attendees if a.status == AttendeeStatus.DRAFT]
        if not drafts:
            if req.status != REQUEST_SENT:
                req.status = REQUEST_SENT
                req.save(update_fields=["status"])
            return SubmitResult(already_sent=True)

        problems = {a.pk: p for a in drafts if (p := submission_problems(a))}
        if problems:
            raise LifecycleError("Не все участники готовы к отправке", problems=problems, conflict=False)

        for attendee in drafts:
            _move(attendee, AttendeeStatus.SUBMITTED)
            attendee.status = AttendeeStatus.SUBMITTED
            attendee.review_comment = ""
            attendee.save(update_fields=["status", "review_comment"])
            _audit_transition(user, ip, attendee, AttendeeStatus.DRAFT, AttendeeStatus.SUBMITTED)

        req.status = REQUEST_SENT
        req.registration_time = timezone.now()
        req.save(update_fields=["status", "registration_time"])
        audit_log(
            user=user, action="request.send", obj_type="Request", obj_id=str(req.pk), ip=ip or "",
            extra={"submitted": [a.pk for a in drafts]},
        )
        return SubmitResult(submitted=drafts)


def start_review(attendee_id, user, ip=None):
    """submitted → in_review. Повтор для уже взятого — без изменений."""
    with transaction.atomic():
        attendee = _locked_attendee(attendee_id)
        if attendee.status == AttendeeStatus.IN_REVIEW:
            return attendee
        _move(attendee, AttendeeStatus.IN_REVIEW)
        old = attendee.status
        attendee.status = AttendeeStatus.IN_REVIEW
        attendee.save(update_fields=["status"])
        _audit_transition(user, ip, attendee, old, attendee.status)
        return attendee


def approve(attendee_id, user, ip=None):
    """in_review → ready (допуск). Повтор для уже одобренного — без изменений."""
    with transaction.atomic():
        attendee = _locked_attendee(attendee_id)
        if attendee.status == AttendeeStatus.READY:
            return attendee
        _move(attendee, AttendeeStatus.READY)
        old = attendee.status
        attendee.status = AttendeeStatus.READY
        attendee.review_comment = ""
        attendee.reviewed_at = timezone.now()
        attendee.reviewed_by = user
        attendee.save(update_fields=["status", "review_comment", "reviewed_at", "reviewed_by"])
        _audit_transition(user, ip, attendee, old, attendee.status)
        return attendee


def return_for_changes(attendee_id, user, reason, ip=None):
    """in_review → draft с причиной; отправленная заявка снова открывается для правки."""
    reason = (reason or "").strip()
    if not reason:
        raise LifecycleError("Укажите причину возврата", conflict=False)
    if len(reason) > RETURN_REASON_MAX:
        raise LifecycleError(f"Причина длиннее {RETURN_REASON_MAX} символов", conflict=False)

    with transaction.atomic():
        attendee = _locked_attendee(attendee_id)
        _move(attendee, AttendeeStatus.DRAFT)
        old = attendee.status
        attendee.status = AttendeeStatus.DRAFT
        attendee.review_comment = reason
        attendee.reviewed_at = timezone.now()
        attendee.reviewed_by = user
        attendee.save(update_fields=["status", "review_comment", "reviewed_at", "reviewed_by"])
        # Причина не пишется в журнал: она может содержать ПД. Журнал хранит факт возврата.
        _audit_transition(user, ip, attendee, old, attendee.status, {"returned": True})

        req = Request.objects.select_for_update().get(pk=attendee.request_id)
        if req.status not in REQUEST_EDITABLE:
            req.status = REQUEST_ACTIVE
            req.save(update_fields=["status"])
        return attendee


def status_summary(attendees):
    """Счётчики по статусам и число возвращённых (черновик с причиной)."""
    summary = {status: 0 for status in (
        AttendeeStatus.DRAFT, AttendeeStatus.SUBMITTED, AttendeeStatus.IN_REVIEW,
        AttendeeStatus.READY, AttendeeStatus.EXPORTED,
    )}
    returned = 0
    for attendee in attendees:
        summary[attendee.status] = summary.get(attendee.status, 0) + 1
        if attendee.status == AttendeeStatus.DRAFT and attendee.review_comment:
            returned += 1
    summary["returned"] = returned
    return summary
