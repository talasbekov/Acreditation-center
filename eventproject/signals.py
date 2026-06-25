"""Story 5.3/5.5 — очистка медиафайлов участника.

``post_delete`` (5.3, AC-5): удаляет ``photo``/``docScan`` с диска при удалении
участника, чтобы не копились orphaned files (файлы без записи в БД).

``pre_save`` (5.5, code-review): удаляет СТАРЫЙ файл при его замене в edit-PATCH —
иначе заменённый ``photo``/``docScan`` оставался бы сиротой на диске (утечка/
накопление PII-медиа). Story 5.3 отложила этот фикс до появления edit-UI с фото
(Story 5.5).

Оба удаления отложены до ``transaction.on_commit``: если транзакция, в которой
произошёл save/delete, откатится, файл НЕ должен исчезнуть (иначе запись есть, а
файла нет). Вне транзакции (autocommit) колбэк выполняется немедленно.

Подключается через ``EventprojectConfig.ready()`` (``eventproject/apps.py``).
"""

import logging

from django.db import transaction
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from eventproject.models import Attendee

logger = logging.getLogger("eventproject")

_MEDIA_FIELDS = ("photo", "docScan")


def _schedule_cleanup(files):
    """Удаляет переданные файлы после commit (graceful при отсутствии на диске)."""
    files = [f for f in files if f]
    if not files:
        return

    def _cleanup():
        for file in files:
            try:
                file.delete(save=False)
            except (FileNotFoundError, OSError):
                logger.warning(
                    "media cleanup: файл %s уже отсутствует на диске",
                    getattr(file, "name", "?"),
                )

    transaction.on_commit(_cleanup)


@receiver(post_delete, sender=Attendee, dispatch_uid="attendee_media_cleanup")
def delete_attendee_files(sender, instance, **kwargs):
    """Удаляет файлы фото/документа удалённого участника (Story 5.3, AC-5)."""
    _schedule_cleanup(getattr(instance, field, None) for field in _MEDIA_FIELDS)


@receiver(pre_save, sender=Attendee, dispatch_uid="attendee_media_replace_cleanup")
def delete_replaced_attendee_files(sender, instance, **kwargs):
    """Удаляет СТАРЫЙ файл при замене ``photo``/``docScan`` в edit-PATCH (Story 5.5).

    На create (``instance.pk`` пуст) — пропуск: старого файла нет. Сравниваем имена
    старого и нового значения поля; при изменении (включая очистку) старый файл
    планируется к удалению после commit (от rollback-гонки). Один доп. SELECT на
    update — приемлемо для низкочастотных мутаций участника.
    """
    if not instance.pk:
        return
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return  # новая запись с заданным pk — старого файла на диске нет

    replaced = []
    for field in _MEDIA_FIELDS:
        old_file = getattr(old, field, None)
        old_name = getattr(old_file, "name", None)
        new_name = getattr(getattr(instance, field, None), "name", None)
        if old_name and old_name != new_name:
            replaced.append(old_file)
    _schedule_cleanup(replaced)
