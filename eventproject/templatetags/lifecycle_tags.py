"""Подписи статусов участника для операторских HTML-страниц (RU/KZ/EN).

Казахские подписи требуют проверки носителем языка.
"""

from django import template

register = template.Library()

_LABELS = {
    "ru": {
        "draft": "Черновик", "returned": "Возвращён на доработку", "submitted": "Отправлен на проверку",
        "in_review": "На проверке", "ready": "Допущен", "exported": "Допущен, передан в службу",
        "reason": "Причина",
    },
    "kz": {
        "draft": "Жоба", "returned": "Түзетуге қайтарылды", "submitted": "Тексеруге жіберілді",
        "in_review": "Тексерілуде", "ready": "Рұқсат етілді", "exported": "Рұқсат етілді, қызметке жіберілді",
        "reason": "Себебі",
    },
    "en": {
        "draft": "Draft", "returned": "Returned for changes", "submitted": "Sent for review",
        "in_review": "Under review", "ready": "Approved", "exported": "Approved, transferred",
        "reason": "Reason",
    },
}


def _labels(lang):
    return _LABELS.get(lang, _LABELS["ru"])


@register.filter
def attendee_state(attendee, lang="ru"):
    key = "returned" if attendee.status == "draft" and attendee.review_comment else attendee.status
    return _labels(lang).get(key, attendee.status)


_TONES = {
    "draft": "info", "returned": "danger", "submitted": "warning",
    "in_review": "warning", "ready": "success", "exported": "success",
}


@register.filter
def attendee_tone(attendee):
    """Этап D: цвет плашки статуса (как StatusBadge в SPA); текст даёт attendee_state."""
    key = "returned" if attendee.status == "draft" and attendee.review_comment else attendee.status
    return _TONES.get(key, "info")


@register.filter
def reason_label(lang="ru"):
    return _labels(lang)["reason"]
