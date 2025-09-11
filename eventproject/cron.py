import logging
import json

from asgiref.sync import async_to_sync
from django.test import RequestFactory

from eventproject.models import Event, Operator
from eventproject.views.integration.integrate import kazexpo_receive
from eventproject.views.integration.integrate_kazenergy import kazenergy_receive

logger = logging.getLogger(__name__)


def kazexpo_import_job():
    """Ежеминутный импорт из Avalon, вызывается через django‑crontab."""

    # 1. Получаем тестовый GET-запрос
    rf = RequestFactory()
    request = rf.get('/')

    # 2. Выбираем Event и Operator (здесь можно параметризовать)
    try:
        event = Event.objects.get(pk=3)
        operator = Operator.objects.get(pk=1)
    except (Event.DoesNotExist, Operator.DoesNotExist) as exc:
        logger.error("Cron job aborted: %s", exc)
        return

    logger.info("Starting kazexpo_import_job: event=%s operator=%s", event.id, operator.id)

    # 3. Вызываем view для импорта
    try:
        # response = async_to_sync(kazexpo_receive)(request, event.id, operator.id)
        response = async_to_sync(kazenergy_receive)(request, event.id, operator.id)
        status = getattr(response, 'status_code', None)
        content = getattr(response, 'content', b'').decode('utf-8', errors='ignore')
        logger.info("kazexpo_receive response: status=%s, body=%s", status, content)

        # 4. Пытаемся парсить JSON, чтобы получить список созданных ID
        try:
            data = json.loads(content)
            created = data.get('created_ids')
            pages = data.get('pages_fetched')
            logger.info("Import result: created_ids=%s, pages_fetched=%s", created, pages)
        except json.JSONDecodeError:
            logger.warning("Response is not valid JSON, skipping parse")

    except Exception as exc:
        logger.exception("KazExpo cron import failed: %s", exc)
