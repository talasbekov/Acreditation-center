"""Справочники для SPA-формы участника (этап D): `GET /api/v1/directories/`.

Только чтение. Те же справочники, что HTML-форма `gov3.html` получает из контекста:
пол, типы документов, категории участников, страны. Коды — те, что хранятся в
`Attendee.sexId`, `docTypeId`, `stickId`, `countryId`; названия — по-русски.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from directories.models import Category, Country, DocumentType, Sex
from eventproject.permissions import IsOperator


def _rows(queryset, code_field):
    return [{"code": code, "name": name} for code, name in queryset.order_by("name_rus").values_list(code_field, "name_rus")]


@api_view(["GET"])
@permission_classes([IsOperator])
def directories(request):
    return Response(
        {
            "sexes": _rows(Sex.objects.all(), "sex_code"),
            "document_types": _rows(DocumentType.objects.all(), "doc_code"),
            "categories": _rows(Category.objects.all(), "category_code"),
            "countries": _rows(Country.objects.all(), "country_code"),
        }
    )
