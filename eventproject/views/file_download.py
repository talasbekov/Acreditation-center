import logging
import os
import mimetypes

from django.conf import settings
from django.http import HttpResponse, StreamingHttpResponse

from wsgiref.util import FileWrapper

from eventproject.cron import logger
from eventproject.models import Event, Request, Attendee

from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

import json
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import JsonResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from django.views import View
from pathlib import Path
from datetime import timezone as dt_timezone

from eventproject.services import zipstream

reconciliation_logger = logging.getLogger("eventproject.audit")

# from eventproject.tasks import logger, cleanup_old_archives


# class EventArchiveView(UserPassesTestMixin, View):
#     """
#     Класс для работы с архивами событий через Celery
#     """
#
#     def test_func(self):
#         return self.request.user.is_superuser
#
#     def post(self, request, event_id):
#         """Запускает создание архива"""
#         try:
#             # Проверяем, не создается ли уже архив
#             status = cache.get(f"archive_status_{event_id}")
#             if status and status.get('status') == 'processing':
#                 return JsonResponse({
#                     'status': 'already_processing',
#                     'task_id': status.get('task_id'),
#                     'progress': status.get('progress', 0)
#                 })
#
#             # Запускаем задачу
#             task = create_event_archive.delay(event_id, request.user.id)
#
#             return JsonResponse({
#                 'status': 'started',
#                 'task_id': task.id,
#                 'check_url': f'/check_archive_status/{event_id}/'
#             })
#
#         except Exception as e:
#             logger.error(f"Error starting archive task for event {event_id}: {e}")
#             return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
#
#     def get(self, request, event_id):
#         """Скачивает готовый архив"""
#         try:
#             status = cache.get(f"archive_status_{event_id}")
#             if not status or status.get('status') != 'completed':
#                 raise Http404("Archive not ready or not found")
#
#             archive_path = Path(status['archive_path'])
#             if not archive_path.exists():
#                 raise Http404("Archive file not found")
#
#             # Отправляем файл
#             response = FileResponse(
#                 open(archive_path, 'rb'),
#                 as_attachment=True,
#                 filename=f"event_{event_id}.zip",
#                 content_type='application/zip'
#             )
#             return response
#
#         except Exception as e:
#             logger.error(f"Error downloading archive for event {event_id}: {e}")
#             return JsonResponse({'status': 'error', 'message': str(e)}, status=404)


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
@require_http_methods(["GET"])
def check_archive_status(request, event_id):
    """
    Проверяет статус создания архива
    """
    status = cache.get(f"archive_status_{event_id}")

    if not status:
        return JsonResponse({
            'status': 'not_found',
            'message': 'Archive task not found'
        })

    return JsonResponse(status)


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
def download_photos(request, event_id):
    """Все фото и сканы мероприятия одним ZIP, потоком.

    Архив не пишется ни во временный файл, ни в память: `services/zipstream.py`
    складывает его прямо в ответ (без сжатия, CRC считается при отдаче), размер
    известен заранее. Поэтому выгрузка в гигабайты не упирается в диск контейнера
    и не держит воркер до конца сборки. Файл, изменившийся во время передачи,
    обрывает поток — клиент не получит полный архив с неверным содержимым.
    """
    event_dir = Path(settings.MEDIA_ROOT) / f"event_{event_id}"
    if not event_dir.exists():
        return HttpResponse("Директория с фотографиями не найдена", status=404)

    try:
        entries = [
            zipstream.Entry(path.relative_to(event_dir.parent).as_posix(), path.stat().st_size, path=str(path))
            for path in sorted(event_dir.rglob("*.*"))
            if path.is_file() and not path.name.startswith(".")
        ]
    except OSError:
        logger.error("Archive listing failed")
        return HttpResponse("Ошибка при создании архива", status=500)
    if not entries:
        return HttpResponse("Фотографии не найдены", status=404)

    stream = zipstream.ZipStream(entries, timezone.now().astimezone(dt_timezone.utc).timetuple()[:6])
    response = StreamingHttpResponse(stream.iter_bytes(), content_type="application/zip")
    response["Content-Length"] = str(stream.size)
    response["Content-Disposition"] = f'attachment; filename="event_{event_id}.zip"'
    response["Cache-Control"] = "private, no-store"
    return response


# @user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
# def download_photos(request, event_id):
#     """
#     Основная функция скачивания фото - через Celery с fallback на синхронный режим
#     """
#     try:
#         # Сначала проверяем готовый архив
#         status = cache.get(f"archive_status_{event_id}")
#
#         if status and status.get('status') == 'completed':
#             archive_path = Path(status['archive_path'])
#             if archive_path.exists():
#                 # Готовый архив есть - сразу отдаем
#                 return FileResponse(
#                     open(archive_path, 'rb'),
#                     as_attachment=True,
#                     filename=f"event_{event_id}.zip",
#                     content_type='application/zip'
#                 )
#
#         # Проверяем, не создается ли уже архив
#         if status and status.get('status') == 'processing':
#             # Показываем страницу со статусом
#             context = {
#                 'event_id': event_id,
#                 'task_id': status.get('task_id'),
#                 'progress': status.get('progress', 0),
#                 'message': f'Архив создается... {status.get("progress", 0)}%'
#             }
#             return render(request, 'creating_archive.html', context)
#
#         # Архива нет - пробуем создать через Celery
#         try:
#             cleanup_old_archives()
#             task = create_event_archive.delay(event_id, request.user.id)
#             context = {
#                 'event_id': event_id,
#                 'task_id': task.id,
#                 'progress': 0,
#                 'message': 'Запуск создания архива...'
#             }
#             return render(request, 'creating_archive.html', context)
#
#         except Exception as celery_error:
#             logger.warning(f"Celery unavailable for event {event_id}, falling back to sync: {celery_error}")
#
#             # Fallback - создаем синхронно
#             return _create_archive_sync(event_id)
#
#     except Exception as e:
#         logger.error(f"Error in download_photos for event {event_id}: {e}")
#         return HttpResponse(f"Ошибка при скачивании: {str(e)}", status=500)
#
#
# def _create_archive_sync(event_id):
#     """
#     Синхронное создание архива (fallback)
#     """
#     try:
#         # Пути
#         event_dir = Path(settings.MEDIA_ROOT) / f"event_{event_id}"
#
#         # Проверяем существование директории с фото
#         if not event_dir.exists():
#             return HttpResponse("Директория с фотографиями не найдена", status=404)
#
#         # Собираем все файлы
#         files = []
#         for file_path in event_dir.rglob('*.*'):
#             if file_path.is_file() and not file_path.name.startswith('.'):
#                 files.append(file_path)
#
#         if not files:
#             return HttpResponse("Фотографии не найдены", status=404)
#
#         # Создаем временный архив
#         with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
#             tmp_path = tmp_file.name
#
#         try:
#             # Создаем архив
#             with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as zipf:
#                 for file_path in files:
#                     arcname = file_path.relative_to(event_dir.parent)
#                     zipf.write(file_path, arcname)
#
#             # Проверяем размер архива
#             archive_size = Path(tmp_path).stat().st_size
#             if archive_size == 0:
#                 return HttpResponse("Архив пуст", status=404)
#
#             # Отправляем файл
#             response = FileResponse(
#                 open(tmp_path, 'rb'),
#                 as_attachment=True,
#                 filename=f"event_{event_id}.zip",
#                 content_type='application/zip'
#             )
#
#             # Планируем удаление временного файла
#             import atexit
#             atexit.register(lambda: Path(tmp_path).unlink(missing_ok=True))
#
#             return response
#
#         except Exception as e:
#             # Удаляем временный файл при ошибке
#             Path(tmp_path).unlink(missing_ok=True)
#             raise e
#
#     except Exception as e:
#         logger.error(f"Error creating sync archive for event {event_id}: {e}")
#         return HttpResponse(f"Ошибка при создании архива: {str(e)}", status=500)

# @user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
# def download_photos(request, event_id):
#     """
#     Простая функция для скачивания фото - сразу создает и отдает архив
#     """
#     try:
#         # Проверяем существование события (опционально)
#         # from directories.models import Event
#         # event = Event.objects.get(id=event_id)
#
#         # Пути
#         event_dir = Path(settings.MEDIA_ROOT) / f"event_{event_id}"
#
#         # Проверяем существование директории с фото
#         if not event_dir.exists() or not any(event_dir.rglob('*.*')):
#             return HttpResponse("Фотографии для данного события не найдены", status=404)
#
#         # Создаем временный архив
#         archive_path = Path(settings.MEDIA_ROOT) / "temp" / f"event_{event_id}.zip"
#         archive_path.parent.mkdir(exist_ok=True)
#
#         # Создаем архив
#         with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
#             for file_path in event_dir.rglob('*.*'):
#                 if file_path.is_file() and not file_path.name.startswith('.'):
#                     # Добавляем файл в архив с относительным путем
#                     arcname = file_path.relative_to(event_dir)
#                     zipf.write(file_path, arcname)
#
#         # Проверяем размер архива
#         archive_size = archive_path.stat().st_size
#         if archive_size == 0:
#             archive_path.unlink(missing_ok=True)
#             return HttpResponse("Архив пуст", status=404)
#
#         # Отправляем файл
#         response = FileResponse(
#             open(archive_path, 'rb'),
#             as_attachment=True,
#             filename=f"event_{event_id}.zip",
#             content_type='application/zip'
#         )
#
#         # Удаляем временный файл после отправки (в фоне)
#         def cleanup():
#             try:
#                 if archive_path.exists():
#                     archive_path.unlink()
#             except:
#                 pass
#
#         # Планируем удаление через 10 минут
#         import threading
#         timer = threading.Timer(600.0, cleanup)
#         timer.start()
#
#         return response
#
#     except Exception as e:
#         logger.error(f"Error creating archive for event {event_id}: {e}")
#         return HttpResponse(f"Ошибка при создании архива: {str(e)}", status=500)

def _reconcile_event_ids(event_id, statuses):
    event = get_object_or_404(Event.objects.only("id"), pk=event_id)
    rows = list(Attendee.objects.filter(
        request__event=event, request__status__in=statuses,
    ).order_by("pk").values("id", "request"))
    reconciliation_logger.info("reconciliation.event", extra={"attendees": len(rows)})
    return JsonResponse({"id": event.pk, "attendees": rows})


@never_cache
@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
@require_POST
@csrf_protect
def download_json(request, event_id):
    return _reconcile_event_ids(event_id, ["Sent"])


@never_cache
@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
@require_POST
@csrf_protect
def download_guests_json(request, event_id):
    return _reconcile_event_ids(event_id, ["Sent"])


@never_cache
@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
@require_POST
@csrf_protect
def download_all_guests_json(request, event_id):
    return _reconcile_event_ids(event_id, ["Sent", "Exported"])


@never_cache
@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
@require_POST
@csrf_protect
def download_request_json(request, request_id):
    req = get_object_or_404(Request.objects.only("id", "event_id"), pk=request_id)
    rows = list(Attendee.objects.filter(request=req).order_by("pk").values("id", "request"))
    reconciliation_logger.info("reconciliation.request", extra={"attendees": len(rows)})
    return JsonResponse({"id": req.pk, "event": str(req.event_id), "attendees": rows})


# @user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
# def download_photos(request, event_id):
#     context_dict = {}
#     try:
#         if os.path.exists("event_" + str(event_id) + ".zip"):
#             os.remove("event_" + str(event_id) + ".zip")
#             print("The file has been deleted successfully")
#         else:
#             print("The file does not exist!")
#         dir_name = "media/event_" + str(event_id)
#         if not os.path.isdir(dir_name):
#             return HttpResponse("No photos uploaded yet")
#
#         zip_address = "media/event_" + str(event_id)
#         file = open(zip_address + "/test.txt", "w")
#         file.close()
#
#         # Архивируем директорию, указывая корень архива как родительскую директорию
#         shutil.make_archive(f"media/event_{event_id}", "zip", "media", f"event_{event_id}")
#
#         # Открываем и отправляем созданный архив
#         zip = open(dir_name + ".zip", "rb")
#         response = FileResponse(zip)
#         return response
#
#     except Request.DoesNotExist:
#         return HttpResponse("Could not find event")
#     return render(request, "event.html", context_dict)


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
def download_file(request, event_id):
    the_file = "event_" + str(event_id) + ".zip"
    try:
        filename = os.path.basename(the_file)
        chunk_size = 8192
        response = StreamingHttpResponse(
            FileWrapper(open(the_file, "rb"), chunk_size),
            content_type=mimetypes.guess_type(the_file)[0],
        )
        response["Content-Length"] = os.path.getsize(the_file)
        response["Content-Disposition"] = "attachment; filename=%s" % filename
        return response
    except FileNotFoundError:
        # M5: реальное исключение при отсутствии файла (было: except Request.DoesNotExist — недостижимо).
        return HttpResponse("Архив не найден", status=404)
    except Exception as e:
        logger.error("Archive download failed")
        return HttpResponse("Ошибка при скачивании файла", status=500)


# @user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
# def prepare_file(request, event_id):
#     context_dict = {}
#     try:
#         p = Process(target=download_photos_async, args=(event_id,))
#         p.start()
#         context_dict[
#             "success_message"
#         ] = "Архивируется файлы, через какое-то время обновите страницу"
#     except Request.DoesNotExist:
#         return HttpResponse("Could not find event")
#     return render(request, "event.html", context_dict)
