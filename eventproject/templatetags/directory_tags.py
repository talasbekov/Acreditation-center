"""Подпись из справочника по коду без перебора справочника на каждой строке (P2).

Раньше карточки участников выводили страну, пол, категорию и тип документа
вложенным `{% for %}` по всему справочнику — для заявки из 300 участников и
~250 стран это десятки тысяч итераций на один рендер. Тег строит словарь
«код → подпись» один раз за рендер шаблона и дальше берёт значение по ключу.

    {% dir_name countries "country_code" attendee.countryId "name_rus" as country %}
"""

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def dir_name(context, rows, code_field, code, name_field):
    """Подпись `name_field` строки справочника `rows` с `code_field == code`; "" если нет."""
    if rows is None or code in (None, ""):
        return ""
    cache = context.render_context.setdefault("_dir_name_index", {})
    key = (id(rows), code_field, name_field)
    index = cache.get(key)
    if index is None:
        index = {}
        for row in rows:
            # Первое совпадение, как у прежнего цикла с выводом первой строки.
            index.setdefault(str(getattr(row, code_field)), getattr(row, name_field))
        # Держим ссылку на rows, чтобы id() не переиспользовался другим объектом за рендер.
        cache[key] = index
        cache.setdefault("_rows_refs", []).append(rows)
    return index.get(str(code), "")
