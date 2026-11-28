"""Язык страниц оператора: RU (корень), KZ (/kz/…), EN (/en/…).

Шаблоны тоже общие: строки интерфейса пишутся по-русски в `{% t "…" %}`, казахский и
английский варианты лежат в `eventproject/ui_text.py`.

Раньше каждая языковая версия была отдельной копией обработчиков (`kz_event/views.py`,
`en_event/views.py`), и копии расходились: KZ/EN не учитывали блокировку входа,
разлогинивали после смены пароля, по-разному реагировали на лимит запросов. Теперь
обработчик один, язык приходит из URL (`kwargs={"lang": "kz"}`), а отличаются только
адреса, шаблоны и тексты — они собраны здесь.

Казахские тексты, добавленные при объединении (помечены `# KZ: проверить`), написаны
без носителя языка.
"""

from functools import wraps

from django.contrib.auth.views import redirect_to_login

LANGS = ("ru", "kz", "en")
DEFAULT = "ru"

# Поле названия в справочниках (Country, City, …) для сортировки списков.
NAME_FIELD = {"ru": "name_rus", "kz": "name_kaz", "en": "name_eng"}


def norm(lang):
    return lang if lang in LANGS else DEFAULT


def prefix(lang):
    """Префикс адреса: "" для RU, "/kz" и "/en" для остальных."""
    lang = norm(lang)
    return "" if lang == DEFAULT else f"/{lang}"


def url(lang, path):
    return prefix(lang) + path


def template(lang, name):
    """Шаблон страницы. Шаблоны общие для трёх языков; язык берут из контекста."""
    return name


def request_lang(request):
    """Язык страницы по URL: `{"lang": "kz"}` из urls.py, иначе RU."""
    match = getattr(request, "resolver_match", None)
    return norm((match.kwargs.get("lang") if match else None) or DEFAULT)


def context(request):
    """Контекст-процессор: язык, префикс адресов, поле названий справочников и адреса
    этой же страницы на других языках (переключатель языка сохраняет сценарий, отчёт 05)."""
    lang = request_lang(request)
    path = request.path
    for other in LANGS:
        if other != DEFAULT and (path == f"/{other}" or path.startswith(f"/{other}/")):
            path = path[len(other) + 1:] or "/"
            break
    lang_paths = {code: prefix(code) + path for code in LANGS}
    return {"lang": lang, "lp": prefix(lang), "name_field": NAME_FIELD[lang], "lang_paths": lang_paths}


def login_required(view):
    """`login_required`, который отправляет на вход той же языковой версии."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), url(kwargs.get("lang", DEFAULT), "/user_login/"))
        return view(request, *args, **kwargs)

    return wrapper


_TEXT = {
    # Вход
    "login_bad": {
        "ru": "Неправильный логин или пароль",
        "kz": "Логин, не құпиясыз сәйкес келмейді",
        "en": "Wrong username or password",
    },
    "login_locked": {
        "ru": "Аккаунт временно заблокирован из-за множества неудачных попыток входа. Повторите попытку позже.",
        "kz": "Сәтсіз кіру әрекеттері көп болғандықтан, аккаунт уақытша бұғатталды. Кейінірек қайталап көріңіз.",  # KZ: проверить
        "en": "The account is temporarily locked after too many failed login attempts. Please try again later.",
    },
    "account_disabled": {
        "ru": "Аккаунт деактивирован",
        "kz": "Аккаунт өшірілген",  # KZ: проверить
        "en": "The account is deactivated",
    },
    # Смена пароля
    "pw_mismatch": {
        "ru": "Введите новый пароль два раза",
        "kz": "Жаңа құпиясөздер сәйкес келмейді",
        "en": "New passwords do not match",
    },
    "pw_changed": {
        "ru": "Пароль успешно изменен",
        "kz": "Құпиясөз сәтті өзгертілді",
        "en": "Password is successfully changed",
    },
    "pw_wrong_old": {
        "ru": "Не удалось подтвердить данные",
        "kz": "Ескі құпиясөз дұрыс емес",
        "en": "Wrong old password",
    },
    "pw_failed": {
        "ru": "Не удалось изменить пароль. Попробуйте ещё раз.",
        "kz": "Құпиясөзді өзгерту мүмкін болмады. Қайталап көріңіз.",
        "en": "Could not change the password. Please try again.",
    },
    # Заявка
    "sent_at": {
        "ru": "Отправлено {time}",
        "kz": "{time} жіберілді",
        "en": "Sent {time}",
    },
    "ready_to_send": {
        "ru": "Заявка готова к отправлению",
        "kz": "Өтініш жіберуге дайын",
        "en": "Request is ready to send",
    },
    "send_warning": {
        "ru": "Внимание!!! Отправка заявки не гарантирует допуск участника в зону проведения охранного мероприятия в установленную дату",
        "kz": "Назар аударыңыз!!! Өтініштің жіберілімі шараға кіргізілуге кепіл болмайды",
        "en": "Attention! Sending the application does not guarantee entrance to the event",
    },
    # Добавление участника: префикс отказа и причины
    "add_failed": {
        "ru": "Не удалось добавить. {reason}",
        "kz": "Қатысушы қосылмады. {reason}",
        "en": "Could not add. {reason}",
    },
    "bad_date_format": {
        "ru": "Проверьте формат дат (ГГГГ-ММ-ДД).",
        "kz": "Күн форматын тексеріңіз (ЖЖЖЖ-АА-КК).",
        "en": "Check the date format (YYYY-MM-DD).",
    },
    "doc_not_started": {
        "ru": "Дата выдачи документа еще не наступила",
        "kz": "Құжаттың берілген күні қате",
        "en": "Wrong document issued date",
    },
    "doc_expired": {
        "ru": "Истек срок документа",
        "kz": "Құжаттың мерзімі өтіп кетті",
        "en": "Wrong document expiry date",
    },
    "dob_future": {
        "ru": "Проверьте дату рождения",
        "kz": "Туған күн қате еңгізілген",
        "en": "Wrong date of birth",
    },
    "added": {
        "ru": "Участник {surname} {firstname} был успешно добавлен",
        "kz": "Қатысушы {surname} {firstname} сәтті қосылды",
        "en": "Attendee {transcription} is successfully added to the request",
    },
    # Удаление
    "deleted": {
        "ru": "Участник {surname} {firstname} был успешно удален",
        "kz": "Қатысушы {surname} {firstname} жүйеден өшірілді",
        "en": "Attendee {surname} {firstname} is deleted",
    },
    "request_deleted": {
        "ru": "Заявка {name} удалена, так как в ней не осталось участников",
        "kz": "{name} өтінімінде қатысушы қалмағандықтан, ол өшірілді",  # KZ: проверить
        "en": "Request {name} was deleted because no attendees were left",
    },
    "delete_failed": {
        "ru": "Не удалось удалить участника",
        "kz": "Қатысушыны өшіру мүмкін болмады",  # KZ: проверить
        "en": "Could not delete the attendee",
    },
    # ИИН (коды из validators/iin.py и validators/residency.py; русский текст берётся
    # из валидатора, здесь — для полноты словаря и проверки тестом).
    "iin_required": {
        "ru": "ИИН обязателен для граждан Казахстана",
        "kz": "Қазақстан азаматтары үшін ЖСН міндетті",  # KZ: проверить
        "en": "IIN is required for citizens of Kazakhstan",
    },
    "iin_format": {
        "ru": "ИИН должен содержать ровно 12 цифр.",
        "kz": "ЖСН дәл 12 цифрдан тұруы керек.",  # KZ: проверить
        "en": "The IIN must contain exactly 12 digits.",
    },
    "iin_checksum": {
        "ru": "ИИН некорректен: неверная контрольная цифра.",
        "kz": "ЖСН қате: бақылау цифры дұрыс емес.",  # KZ: проверить
        "en": "Invalid IIN: wrong check digit.",
    },
    "iin_date_invalid": {
        "ru": "ИИН некорректен: недопустимая дата рождения.",
        "kz": "ЖСН қате: туған күні жарамсыз.",  # KZ: проверить
        "en": "Invalid IIN: impossible date of birth.",
    },
    "iin_dob_mismatch": {
        "ru": "Дата рождения в ИИН ({iin_dob}) не совпадает с введённой ({entered_dob}). Проверьте дату.",
        "kz": "ЖСН-дағы туған күн ({iin_dob}) енгізілген күнмен ({entered_dob}) сәйкес келмейді. Күнді тексеріңіз.",  # KZ: проверить
        "en": "The date of birth in the IIN ({iin_dob}) does not match the one entered ({entered_dob}). Check the date.",
    },
}


def text(key, lang=DEFAULT, **kwargs):
    value = _TEXT[key][norm(lang)]
    return value.format(**kwargs) if kwargs else value


def residency_error(result, lang=DEFAULT):
    """Ошибка ИИН/резидентства на языке страницы.

    Русский — дословно из валидатора (его же видит API); KZ/EN — по коду ошибки.
    Неизвестный код — русский текст, чтобы сообщение не пропало.
    """
    if norm(lang) == DEFAULT or result.code not in _TEXT:
        return result.error
    return text(result.code, lang, **(result.params or {}))
