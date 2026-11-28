"""Справочники для SPA-формы участника (этап D): `GET /api/v1/directories/`.

Только чтение. Те же справочники, что HTML-форма `gov3.html` получает из контекста:
пол, типы документов, категории участников, страны. Коды — те, что хранятся в
`Attendee.sexId`, `docTypeId`, `stickId`, `countryId`. Названия — на языке `?lang=`
(ru/kz/en, как у интерфейса); если перевода нет — по-русски. Сортировка — по
русскому названию, чтобы порядок не менялся при переключении языка.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from directories.models import Category, Country, DocumentType, Sex
from eventproject.permissions import IsOperator

_NAME_FIELD = {"ru": "name_rus", "kz": "name_kaz", "en": "name_eng"}


def _rows(queryset, code_field, lang):
    field = _NAME_FIELD.get(lang, "name_rus")
    rows = queryset.order_by("name_rus").values_list(code_field, field, "name_rus")
    return [{"code": code, "name": (name or "").strip() or ru} for code, name, ru in rows]


@api_view(["GET"])
@permission_classes([IsOperator])
def directories(request):
    lang = request.query_params.get("lang", "ru")
    return Response(
        {
            "sexes": _rows(Sex.objects.all(), "sex_code", lang),
            "document_types": _rows(DocumentType.objects.all(), "doc_code", lang),
            "categories": _rows(Category.objects.all(), "category_code", lang),
            "countries": _rows(Country.objects.all(), "country_code", lang),
        }
    )
