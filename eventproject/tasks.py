# eventproject/tasks.py
import json
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
import logging

from asgiref.sync import async_to_sync
from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.test import RequestFactory
from django.utils import timezone

from eventproject.models import Event, Operator
from eventproject.views.integration.integrate_kazenergy import kazenergy_receive

logger = logging.getLogger(__name__)

# @shared_task(bind=True, max_retries=3)
# def create_event_archive(self, event_id, user_id=None):
#     """
#     Создает архив с фотографиями события
#     """
#     try:
#         # Пути
#         event_dir = Path(settings.MEDIA_ROOT) / f"event_{event_id}"
#         archive_dir = Path(settings.MEDIA_ROOT) / "archives"
#         archive_dir.mkdir(exist_ok=True)
#
#         archive_path = archive_dir / f"event_{event_id}.zip"
#
#         # Проверяем существование директории с фото
#         if not event_dir.exists() or not any(event_dir.rglob('*.*')):
#             logger.warning(f"No photos found for event {event_id}")
#             return {'status': 'error', 'message': 'No photos found'}
#
#         # Обновляем статус задачи
#         cache.set(f"archive_status_{event_id}", {
#             'status': 'processing',
#             'progress': 0,
#             'task_id': self.request.id
#         }, timeout=3600)
#
#         # Создаем архив
#         files = list(event_dir.rglob('*.*'))
#         total_files = len([f for f in files if f.is_file() and not f.name.startswith('.')])
#         processed_files = 0
#
#         with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
#             for file_path in files:
#                 if file_path.is_file() and not file_path.name.startswith('.'):
#                     arcname = file_path.relative_to(event_dir)
#                     zipf.write(file_path, arcname)
#                     processed_files += 1
#
#                     # Обновляем прогресс каждые 10 файлов
#                     if processed_files % 10 == 0 or processed_files == total_files:
#                         progress = int((processed_files / total_files) * 100) if total_files > 0 else 100
#                         cache.set(f"archive_status_{event_id}", {
#                             'status': 'processing',
#                             'progress': progress,
#                             'task_id': self.request.id
#                         }, timeout=3600)
#
#         # Проверяем размер архива
#         archive_size = archive_path.stat().st_size
#         if archive_size == 0:
#             archive_path.unlink(missing_ok=True)
#             return {'status': 'error', 'message': 'Archive is empty'}
#
#         # Проверяем лимит размера
#         max_size = getattr(settings, 'MAX_ARCHIVE_SIZE', 5368709120)  # 5GB по умолчанию
#         if archive_size > max_size:
#             archive_path.unlink(missing_ok=True)
#             size_mb = archive_size / (1024 * 1024)
#             max_mb = max_size / (1024 * 1024)
#             return {'status': 'error', 'message': f'Archive too large: {size_mb:.1f}MB (limit: {max_mb:.1f}MB)'}
#
#         # Сохраняем информацию о готовом архиве
#         archive_info = {
#             'status': 'completed',
#             'progress': 100,
#             'task_id': self.request.id,
#             'archive_path': str(archive_path),
#             'archive_size': archive_size,
#             'created_at': timezone.now().isoformat(),
#             'expires_at': (timezone.now() + timedelta(minutes=1)).isoformat()
#         }
#
#         cache.set(f"archive_status_{event_id}", archive_info, timeout=60)
#
#         logger.info(f"Archive created for event {event_id}: {archive_path}")
#         return archive_info
#
#     except Exception as exc:
#         logger.error(f"Error creating archive for event {event_id}: {exc}")
#         cache.set(f"archive_status_{event_id}", {
#             'status': 'error',
#             'progress': 0,
#             'task_id': self.request.id,
#             'error': str(exc)
#         }, timeout=3600)
#
#         # Повторяем попытку
#         if self.request.retries < self.max_retries:
#             raise self.retry(countdown=60, exc=exc)
#
#         return {'status': 'error', 'message': str(exc)}


@shared_task
def cleanup_old_archives():
    """
    Очищает старые архивы (запускается по расписанию)
    """
    archive_dir = Path(settings.MEDIA_ROOT) / "archives"
    if not archive_dir.exists():
        return

    cutoff_time = timezone.now() - timedelta(hours=2)
    deleted_count = 0

    for archive_file in archive_dir.glob("*.zip"):
        try:
            # Проверяем время создания файла
            file_time = datetime.fromtimestamp(archive_file.stat().st_mtime, tz=timezone.utc)
            if file_time < cutoff_time:
                archive_file.unlink()
                deleted_count += 1
                logger.info(f"Deleted old archive: {archive_file}")
        except Exception as e:
            logger.error(f"Error deleting archive {archive_file}: {e}")

    logger.info(f"Cleanup completed, deleted {deleted_count} archives")
    return deleted_count


@shared_task
def kazexpo_import_job():
    """Ежеминутный импорт из Avalon, вызывается через django‑crontab."""

    # 1. Получаем тестовый GET-запрос
    rf = RequestFactory()
    request = rf.get('/')

    # 2. Выбираем Event и Operator (здесь можно параметризовать)
    try:
        event = Event.objects.get(pk=777)
        operator = Operator.objects.get(pk=1405)
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