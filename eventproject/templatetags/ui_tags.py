"""Теги общих шаблонов RU/KZ/EN: `{% t "…" %}` и `{{ obj|lname:lang }}`.

Язык берётся из контекста (`eventproject.page_lang.context`).
"""

from django import template

from eventproject.ui_text import translate

register = template.Library()

_NAME_FIELD = {"ru": "name_rus", "kz": "name_kaz", "en": "name_eng"}


@register.simple_tag(takes_context=True)
def t(context, text, **kwargs):
    """Строка интерфейса на языке страницы; `{name}`-подстановки — из аргументов тега.

    Результат экранируется как обычная переменная (подстановки — данные пользователя).
    """
    value = translate(text, context.get("lang", "ru"))
    return value.format(**kwargs) if kwargs else value


@register.filter
def lname(obj, lang="ru"):
    """Название объекта (мероприятие, справочник) на языке страницы, с откатом на русское."""
    if obj is None:
        return ""
    value = getattr(obj, _NAME_FIELD.get(lang, "name_rus"), None)
    return value or getattr(obj, "name_rus", "") or ""
