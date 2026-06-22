"""Централизованная пагинация для `/api/v1/` (retro Epic 2 action item).

Возвращает документированный envelope `{count, next, previous, results}`
для всех list-эндпоинтов DRF. Клиент может переопределить размер страницы
через `?page_size=` (с верхним пределом).
"""

from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 500
