"""Воркер фоновых задач: `python manage.py run_jobs` (сервис worker в compose).

Опрашивает очередь (eventproject.models.Job) раз в `--interval` секунд; `--once`
выполняет все ожидающие задачи и выходит.
"""

import signal
import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from eventproject.services import jobs


class Command(BaseCommand):
    help = "Выполнять фоновые задачи из очереди (PDF бейджей)."

    def add_arguments(self, parser):
        parser.add_argument("--interval", type=float, default=2.0)
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        stop = {"flag": False}

        def _stop(*_):
            stop["flag"] = True

        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)
        jobs.requeue_stale()
        self.stdout.write("run_jobs: started")
        while not stop["flag"]:
            close_old_connections()
            job = jobs.claim_next()
            if job is None:
                if options["once"]:
                    break
                time.sleep(options["interval"])
                continue
            jobs.run(job.pk)
        self.stdout.write("run_jobs: stopped")
