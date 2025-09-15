# celery.py (в корневой папке проекта)
import os
from celery import Celery
from django.conf import settings

# Устанавливаем настройки Django для Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eventproject.settings')

app = Celery('eventproject')

# Используем настройки Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматически находим задачи в приложениях
app.autodiscover_tasks()

# Конфигурация задач
app.conf.update(
    # Таймаут задач
    task_soft_time_limit=600,  # 10 минут
    task_time_limit=900,  # 15 минут

    # Настройки роутинга
    task_routes={
        'eventproject.tasks.create_event_archive': {'queue': 'archive'},
        'eventproject.tasks.cleanup_old_archives': {'queue': 'cleanup'},
    },

    # Настройки для разных очередей
    task_default_queue='default',
    task_queues={
        'default': {
            'routing_key': 'default',
        },
        'archive': {
            'routing_key': 'archive',
        },
        'cleanup': {
            'routing_key': 'cleanup',
        },
    },

    # Форматы сериализации
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Almaty',
    enable_utc=True,
)

# Периодические задачи
from celery.schedules import crontab

app.conf.beat_schedule = {
    'cleanup-old-archives': {
        'task': 'eventproject.tasks.cleanup_old_archives',
        'schedule': crontab(hour=2, minute=0),  # Каждый день в 2:00
        'options': {'queue': 'cleanup'}
    },
}
