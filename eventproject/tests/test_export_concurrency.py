"""Story hd-1.2 — идемпотентность экспорта: race-тесты обоих экспорт-путей.

Покрытие AC-2 (PROVE, Postgres-only — на SQLite `select_for_update` молча
деградирует в обычный SELECT, гонка недоказуема → `@skipUnless(postgresql)`):

  • Современный delta-путь (`/export_delta/<event>/<request>/`, D1-guard Story 4.3):
    два одновременных POST → ровно один `ExportLog`, каждый attendee `exported`
    ровно один раз, ровно одна audit-строка `export.download`, проигравший
    получает «нет новых записей».
  • Легаси-путь (`/download_guests_json/<event>/` — эндпоинт gap-analysis §3.2
    Critical): каждый `Request` попадает ровно в один из двух ответов
    (объединение = все, пересечение = пусто), оба 200, в БД все `Exported`
    ровно после одного прохода.

Харнесс — копия `test_decision_concurrency.py` (fe-3.6): `TransactionTestCase`
(реальные коммиты) + `reset_sequences` + `threading.Barrier` (одновременный вход)
+ `connections.close_all()` в тредах + per-thread исключения пере-бросаются после
`join()` (ревью-урок P4 fe-3.6: иначе 500 в треде маскируется под расхождение
данных). Клиенты логинятся в главном треде — окно гонки уже.
"""

import io
import json
import threading
import zipfile
from unittest import skipUnless

from django.contrib.auth.models import User
from django.db import connection, connections
from django.test import Client, TransactionTestCase
from django.utils import timezone

from directories.models import Country, DocumentType, Sex
from eventproject.models import (
    Attendee,
    AuditLog,
    Event,
    ExportLog,
    Operator,
    Request,
)

KZ = "1000000105"
SKIP_REASON = (
    "select_for_update на SQLite деградирует в обычный SELECT — "
    "гонка воспроизводится только на Postgres"
)


def _make_directories():
    Country.objects.create(
        country_code=KZ, name_rus="Казахстан", name_kaz="", name_eng="", country_iso="KZ"
    )
    Sex.objects.create(sex_code="M", name_rus="Мужской", name_kaz="", name_eng="")
    DocumentType.objects.create(doc_code="passport", name_rus="Паспорт", name_kaz="", name_eng="")


def _make_attendee(request_obj, *, surname, status="ready", iin="900101300007"):
    return Attendee.objects.create(
        surname=surname, firstname="Имя", patronymic="О",
        birthDate="1990-01-01", post="Инженер", countryId=KZ,
        docTypeId="passport", docSeries="AA", docNumber="123456",
        docIssue="МВД", sexId="M", visitObjects="Зал",
        transcription="T", request=request_obj,
        iin=iin, is_resident=True, status=status,
        dateAdd=timezone.now(),
    )


class _ParallelClientsMixin:
    """Два залогиненных клиента бьют в один URL одновременно (Barrier)."""

    def _run_parallel_posts(self, clients_paths):
        barrier = threading.Barrier(len(clients_paths))
        results = {}
        errors = {}

        def worker(idx, client, path):
            barrier.wait()  # обе транзакции стартуют одновременно → реальная гонка
            try:
                resp = client.post(path)
                if getattr(resp, "streaming", False):
                    body = b"".join(resp.streaming_content)
                else:
                    body = resp.content
                results[idx] = {
                    "status": resp.status_code,
                    "ctype": resp["Content-Type"],
                    "body": body,
                }
            except Exception as exc:  # P4 fe-3.6: сбой воркера не должен молча исчезать
                errors[idx] = exc
            finally:
                connections.close_all()  # закрыть per-thread соединение

        threads = [
            threading.Thread(target=worker, args=(i, c, p))
            for i, (c, p) in enumerate(clients_paths)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        if errors:  # воркер бросил исключение → падаем громко, не length-mismatch
            raise AssertionError(f"worker thread(s) raised: {errors}")
        return results

    def _logged_in_client(self, user):
        client = Client()
        client.force_login(user)
        return client


# ═══════════════════════════════════════════════════════════════════════════
# AC-2 — современный delta-путь: D1-guard (Story 4.3) ДОКАЗЫВАЕТСЯ, не меняется
# ═══════════════════════════════════════════════════════════════════════════
@skipUnless(connection.vendor == "postgresql", SKIP_REASON)
class ModernExportDeltaRaceTests(_ParallelClientsMixin, TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        _make_directories()
        self.event = Event.objects.create(name_rus="E1", title="Event 1", event_code="T1")
        self.super_user = User.objects.create_user("super", password="Pass123!")
        Operator.objects.create(
            user=self.super_user, role="superoperator", patronymic="С",
            phone_number="+70000000001", workplace="HQ",
        )
        self.op_user = User.objects.create_user("op", password="Pass123!")
        self.operator = Operator.objects.create(
            user=self.op_user, role="operator", patronymic="О",
            phone_number="+70000000002", workplace="HQ",
        )
        self.category = Request.objects.create(
            name="Охрана", event=self.event, status="Sent",
            created_by=self.operator, registration_time=timezone.now(),
        )
        self.a1 = _make_attendee(self.category, surname="Первый")
        self.a2 = _make_attendee(self.category, surname="Второй")

    def test_parallel_export_delta_exactly_one_wins(self):
        path = f"/export_delta/{self.event.id}/{self.category.id}/"
        results = self._run_parallel_posts([
            (self._logged_in_client(self.super_user), path),
            (self._logged_in_client(self.super_user), path),
        ])

        # Оба 200: победитель — ZIP, проигравший — текст «нет новых записей».
        self.assertEqual([r["status"] for r in results.values()], [200, 200])
        zips = [r for r in results.values() if r["ctype"] == "application/zip"]
        texts = [r for r in results.values() if r["ctype"].startswith("text/plain")]
        self.assertEqual(len(zips), 1, f"ровно один ZIP-победитель, got: {results}")
        self.assertEqual(len(texts), 1)
        self.assertIn("Нет", texts[0]["body"].decode("utf-8"))

        # Ровно один ExportLog; каждый attendee выгружен ровно один раз.
        self.assertEqual(ExportLog.objects.count(), 1)
        log = ExportLog.objects.get()
        self.assertEqual(log.attendee_count, 2)
        data = json.loads(zipfile.ZipFile(io.BytesIO(zips[0]["body"])).read("attendees.json"))
        exported_ids = [o["attendee_id"] for o in data]
        self.assertEqual(sorted(exported_ids), sorted([self.a1.id, self.a2.id]))
        self.assertEqual(len(exported_ids), len(set(exported_ids)))  # без дублей
        for att in (self.a1, self.a2):
            att.refresh_from_db()
            self.assertEqual(att.status, "exported")

        # Ровно одна durable audit-строка export.download (не две).
        self.assertEqual(AuditLog.objects.filter(action="export.download").count(), 1)


# ═══════════════════════════════════════════════════════════════════════════
# AC-2 — легаси-путь: guard hd-1.2 (BUILD) — до него оба ответа несут ВСЕ заявки
# ═══════════════════════════════════════════════════════════════════════════
@skipUnless(connection.vendor == "postgresql", SKIP_REASON)
class LegacyDownloadGuestsRaceTests(_ParallelClientsMixin, TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        _make_directories()
        self.superuser = User.objects.create_superuser(
            username="su", password="pw12345678", email="su@example.com"
        )
        op_user = User.objects.create_user(username="op2", password="pw12345678")
        self.operator = Operator.objects.create(
            user=op_user, patronymic="T", phone_number="+77001234567",
            workplace="office", role="operator",
        )
        self.event = Event.objects.create(
            name_rus="Событие", name_kaz="Оқиға", name_eng="Event",
            event_code="EXP03", city_code="ALA",
        )
        # По одному участнику на заявку: attendee_id в payload однозначно
        # идентифицирует Request (в легаси-объекте участника request_id нет).
        self.attendee_to_request = {}
        self.requests = []
        for i in range(3):
            req = Request.objects.create(
                name=f"Категория {i}", event=self.event, status="Sent",
                created_by=self.operator, registration_time=timezone.now(),
            )
            att = _make_attendee(req, surname=f"Гость{i}")
            self.requests.append(req)
            self.attendee_to_request[att.id] = req.id

    def _request_ids_in_payload(self, body):
        payload = json.loads(body.decode("utf-8"))
        return {self.attendee_to_request[a["attendee_id"]] for a in payload["attendees"]}

    def test_parallel_download_guests_each_request_exported_once(self):
        path = f"/download_guests_json/{self.event.id}/"
        results = self._run_parallel_posts([
            (self._logged_in_client(self.superuser), path),
            (self._logged_in_client(self.superuser), path),
        ])

        # Оба 200 (проигравший — валидный JSON с пустым attendees, не ошибка).
        self.assertEqual([r["status"] for r in results.values()], [200, 200])

        # Каждый Request — ровно в одном из двух ответов: пересечение пусто,
        # объединение = все Sent-заявки (двойная выгрузка = провал).
        sets = [self._request_ids_in_payload(r["body"]) for r in results.values()]
        all_ids = {r.id for r in self.requests}
        self.assertEqual(sets[0] & sets[1], set(), f"заявки выгружены дважды: {sets}")
        self.assertEqual(sets[0] | sets[1], all_ids)

        # В БД все Exported ровно после одного прохода.
        for req in self.requests:
            req.refresh_from_db()
            self.assertEqual(req.status, "Exported")
        # DB-сторона «одного прохода»: суммарно по audit-строкам выгружено 3, не 6.
        totals = [
            row.extra.get("requests_exported", 0)
            for row in AuditLog.objects.filter(action="export.guests_sent")
        ]
        self.assertEqual(sum(totals), len(all_ids))
