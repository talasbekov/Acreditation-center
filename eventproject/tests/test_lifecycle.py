"""Этап C — единый жизненный цикл: отправка заявки, проверка, возврат, повторная отправка."""

from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from eventproject.models import Attendee, Event, Operator, Request
from eventproject.services import lifecycle

NON_KZ = "1000000840"


class LifecycleFixtures(TestCase):
    def setUp(self):
        self.event = Event.objects.create(name_rus="E", title="E", event_code="E1")
        self.op_user = User.objects.create_user("op", password="x")
        self.operator = Operator.objects.create(
            user=self.op_user, role="operator", patronymic="О", phone_number="+70000000001",
        )
        self.operator.events.add(self.event)
        self.super_user = User.objects.create_user("super", password="x")
        Operator.objects.create(
            user=self.super_user, role="superoperator", patronymic="С", phone_number="+70000000002",
        )
        self.req = Request.objects.create(
            name="R1", event=self.event, status="Active", created_by=self.operator,
            registration_time=timezone.now(),
        )

    def _mk(self, surname="Первый", status="draft", **over):
        data = dict(
            surname=surname, firstname="Тест", post="P", countryId=NON_KZ, is_resident=False,
            docTypeId="passport", docSeries="AA", docIssue="МВД", sexId="M", visitObjects="Зал",
            transcription="T", request=self.req, dateAdd=timezone.now(), status=status,
            photo="p.jpg", docScan="d.jpg",
        )
        data.update(over)
        return Attendee.objects.create(**data)

    def _send(self, prefix=""):
        self.client.force_login(self.op_user)
        return self.client.post(f"{prefix}/send/{self.req.pk}/")

    def _decide(self, attendee, decision, **data):
        self.client.force_login(self.super_user)
        return self.client.post(f"/review/attendee/{attendee.pk}/{decision}/", data)

    def _status(self, attendee):
        attendee.refresh_from_db()
        return attendee.status


class EndToEndReviewTests(LifecycleFixtures):
    def test_two_attendees_one_approved_one_returned_then_resent(self):
        a, b = self._mk("Первый"), self._mk("Второй")

        # Оператор отправляет заявку: оба участника на проверку, заявка Sent.
        self.assertEqual(self._send().status_code, 200)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "Sent")
        self.assertEqual((self._status(a), self._status(b)), ("submitted", "submitted"))

        # Проверяющий берёт обоих, допускает A и возвращает B с причиной.
        for attendee in (a, b):
            self.assertRedirects(self._decide(attendee, "start"), f"/review/{self.event.pk}/", fetch_redirect_response=False)
        self._decide(a, "approve")
        self._decide(b, "return", reason="Скан документа нечитаем")
        self.assertEqual((self._status(a), self._status(b)), ("ready", "draft"))
        b.refresh_from_db()
        self.assertEqual(b.review_comment, "Скан документа нечитаем")
        self.assertEqual(b.reviewed_by, self.super_user)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "Active")

        # Оператор видит раздельные статусы и причину; правит только возвращённого.
        self.client.force_login(self.op_user)
        page = self.client.get(f"/show/{self.req.pk}/").content.decode()
        self.assertIn("Допущен", page)
        self.assertIn("Возвращён на доработку", page)
        self.assertIn("Скан документа нечитаем", page)
        self.assertEqual(self.client.get(f"/update_attendee/{a.pk}/").status_code, 409)
        self.assertEqual(self.client.get(f"/update_attendee/{b.pk}/").status_code, 200)

        # Повторная отправка уходит только для B; причина очищается.
        self._send()
        self.assertEqual((self._status(a), self._status(b)), ("ready", "submitted"))
        b.refresh_from_db()
        self.assertEqual(b.review_comment, "")
        self._decide(b, "start")
        self._decide(b, "approve")
        self.assertEqual(self._status(b), "ready")

        # Оба допущенных уходят в выгрузку (поздняя готовность B учтена).
        from eventproject.services.export import select_ready_attendees
        self.assertEqual(list(select_ready_attendees(self.req).values_list("pk", flat=True)), [a.pk, b.pk])


class SubmitRequestTests(LifecycleFixtures):
    def test_incomplete_attendee_blocks_whole_request_and_names_it(self):
        good = self._mk("Готовый")
        bad = self._mk("Безфото", photo="")
        page = self._send().content.decode()
        self.assertIn("Безфото Тест: нет фото", page)
        self.assertEqual((self._status(good), self._status(bad)), ("draft", "draft"))
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "Active")

    def test_empty_request_is_not_sent(self):
        page = self._send().content.decode()
        self.assertIn("в ней нет участников", page)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "Active")

    def test_resident_without_iin_is_reported(self):
        self._mk("Резидент", countryId="1000000105", is_resident=True, iin=None)
        self.assertIn("ИИН не заполнен или неверен", self._send().content.decode())

    def test_repeated_send_changes_nothing(self):
        a = self._mk()
        self._send()
        self.req.refresh_from_db()
        first_time = self.req.registration_time
        with patch("eventproject.services.lifecycle.audit_log") as audit:
            self._send()
        audit.assert_not_called()
        self.req.refresh_from_db()
        self.assertEqual(self.req.registration_time, first_time)
        self.assertEqual(self._status(a), "submitted")

    def test_localized_send_uses_the_same_rules(self):
        for prefix, phrase in (("/kz", "фото жоқ"), ("/en", "no photo")):
            with self.subTest(prefix=prefix):
                attendee = self._mk("Без", photo="")
                self.assertIn(phrase, self._send(prefix).content.decode())
                self.assertEqual(self._status(attendee), "draft")
                attendee.delete()


class OperatorLockTests(LifecycleFixtures):
    def setUp(self):
        super().setUp()
        self.member = self._mk()
        self._send()

    def test_operator_cannot_edit_or_delete_submitted_attendee(self):
        self.client.force_login(self.op_user)
        self.assertEqual(self.client.get(f"/update_attendee/{self.member.pk}/").status_code, 409)
        for prefix in ("", "/kz", "/en"):
            with self.subTest(prefix=prefix):
                response = self.client.post(f"{prefix}/delete_attendee/", {"attendee_id": self.member.pk})
                self.assertEqual(response.status_code, 409)
        self.assertTrue(Attendee.objects.filter(pk=self.member.pk).exists())

    def test_operator_cannot_add_to_sent_request(self):
        self.client.force_login(self.op_user)
        for prefix in ("", "/kz", "/en"):
            with self.subTest(prefix=prefix):
                self.assertEqual(self.client.get(f"{prefix}/add_attendee/{self.req.pk}/").status_code, 409)

    def test_api_edit_of_submitted_attendee_is_forbidden(self):
        api = APIClient()
        api.force_authenticate(self.op_user)
        response = api.patch(f"/api/v1/attendees/{self.member.pk}/", {"post": "X"}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_operator_page_hides_actions_for_sent_attendee(self):
        self.client.force_login(self.op_user)
        page = self.client.get(f"/show/{self.req.pk}/").content.decode()
        self.assertIn("Отправлен на проверку", page)
        self.assertNotIn(f'value="{self.member.pk}"', page)


class ReviewQueueTests(LifecycleFixtures):
    def setUp(self):
        super().setUp()
        self.member = self._mk()
        self._send()

    def test_queue_lists_submitted_and_opening_changes_nothing(self):
        self.client.force_login(self.super_user)
        page = self.client.get(f"/review/{self.event.pk}/").content.decode()
        self.assertIn("Первый Тест", page)
        self.assertIn("Взять на проверку", page)
        self.assertEqual(self._status(self.member), "submitted")

    def test_approve_requires_taking_into_review_first(self):
        self._decide(self.member, "approve")
        self.assertEqual(self._status(self.member), "submitted")

    def test_return_requires_reason(self):
        self._decide(self.member, "start")
        response = self._decide(self.member, "return", reason="   ")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self._status(self.member), "in_review")
        page = self.client.get(f"/review/{self.event.pk}/").content.decode()
        self.assertIn("Укажите причину возврата", page)

    def test_repeated_decisions_are_idempotent(self):
        self._decide(self.member, "start")
        self._decide(self.member, "start")
        self._decide(self.member, "approve")
        with patch("eventproject.services.lifecycle.audit_log") as audit:
            self._decide(self.member, "approve")
        audit.assert_not_called()
        self.assertEqual(self._status(self.member), "ready")

    def test_operator_and_anonymous_cannot_review(self):
        self.client.force_login(self.op_user)
        self.assertEqual(self.client.get(f"/review/{self.event.pk}/").status_code, 403)
        self.assertEqual(self.client.post(f"/review/attendee/{self.member.pk}/start/").status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.post(f"/review/attendee/{self.member.pk}/start/").status_code, 302)
        self.assertEqual(self._status(self.member), "submitted")

    def test_decision_requires_post_and_known_action(self):
        self.client.force_login(self.super_user)
        self.assertEqual(self.client.get(f"/review/attendee/{self.member.pk}/start/").status_code, 405)
        self.assertEqual(self.client.post(f"/review/attendee/{self.member.pk}/delete/").status_code, 404)

    def test_return_reason_is_not_written_to_the_audit_log(self):
        self._decide(self.member, "start")
        with patch("eventproject.services.lifecycle.audit_log") as audit:
            self._decide(self.member, "return", reason="Паспорт 123 просрочен")
        logged = repr([c.kwargs for c in audit.call_args_list])
        self.assertNotIn("Паспорт 123", logged)
        self.assertIn("'returned': True", logged)

    def test_dashboard_links_to_queue(self):
        self.client.force_login(self.super_user)
        page = self.client.get(f"/dashboard/{self.event.pk}/").content.decode()
        self.assertIn(f"/review/{self.event.pk}/", page)


class ReviewApiTests(LifecycleFixtures):
    def setUp(self):
        super().setUp()
        self.member = self._mk()
        self._send()
        self.api = APIClient()

    def _post(self, user, action, **data):
        self.api.force_authenticate(user)
        return self.api.post(f"/api/v1/attendees/{self.member.pk}/{action}/", data, format="json")

    def test_superoperator_review_path(self):
        self.assertEqual(self._post(self.super_user, "start-review").json()["status"], "in_review")
        self.assertEqual(self._post(self.super_user, "approve").json()["status"], "ready")

    def test_return_needs_reason_and_reopens_request(self):
        self._post(self.super_user, "start-review")
        self.assertEqual(self._post(self.super_user, "return").status_code, 400)
        response = self._post(self.super_user, "return", reason="Нет подписи")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "draft")
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "Active")

    def test_operator_cannot_decide(self):
        self.assertEqual(self._post(self.op_user, "start-review").status_code, 403)
        self.assertEqual(self._status(self.member), "submitted")

    def test_invalid_transition_is_conflict(self):
        self.assertEqual(self._post(self.super_user, "approve").status_code, 409)

    def test_spa_sees_return_reason_and_resubmits(self):
        self._post(self.super_user, "start-review")
        self._post(self.super_user, "return", reason="Нет подписи")
        self.api.force_authenticate(self.op_user)
        detail = self.api.get(f"/api/v1/attendees/{self.member.pk}/").json()
        self.assertEqual(detail["review_comment"], "Нет подписи")
        row = self.api.get("/api/v1/attendees/").json()["results"][0]
        self.assertTrue(row["returned"])
        self.assertNotIn("review_comment", row)
        # Причину клиент не перезаписывает.
        self.api.patch(f"/api/v1/attendees/{self.member.pk}/", {"review_comment": "x"}, format="json")
        self.member.refresh_from_db()
        self.assertEqual(self.member.review_comment, "Нет подписи")
        response = self._post(self.op_user, "submit")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "submitted")
        self.assertEqual(response.json()["review_comment"], "")
        row = self.api.get("/api/v1/attendees/").json()["results"][0]
        self.assertFalse(row["returned"])

    def test_submit_refusal_names_missing_items_in_words(self):
        incomplete = self._mk("Неполный", photo="", docScan="")
        self.api.force_authenticate(self.op_user)
        response = self.api.post(f"/api/v1/attendees/{incomplete.pk}/submit/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("нет фото, нет скана документа", response.json()["detail"])
        self.assertNotIn("doc_scan", response.json()["detail"])


class StatusSummaryTests(LifecycleFixtures):
    def test_summary_counts_returned_separately(self):
        self._mk("A", status="draft", review_comment="причина")
        self._mk("B", status="draft")
        self._mk("C", status="ready")
        summary = lifecycle.status_summary(Attendee.objects.all())
        self.assertEqual((summary["draft"], summary["returned"], summary["ready"]), (2, 1, 1))


class SentTimeDisplayTests(LifecycleFixtures):
    def test_local_time_format(self):
        moment = datetime(2026, 11, 24, 12, 47, 32, 552744, tzinfo=dt_timezone.utc)
        with override_settings(TIME_ZONE="UTC"):
            self.assertEqual(lifecycle.local_time(moment), "24.11.2026 12:47")
        self.assertEqual(lifecycle.local_time(None), "")

    def test_sent_request_shows_readable_time_in_three_languages(self):
        moment = datetime(2026, 11, 24, 12, 47, 32, 552744, tzinfo=dt_timezone.utc)
        Request.objects.filter(pk=self.req.pk).update(status="Sent", registration_time=moment)
        expected = timezone.localtime(moment).strftime("%d.%m.%Y %H:%M")
        self.client.force_login(self.op_user)
        for prefix in ("", "/kz", "/en"):
            page = self.client.get(f"{prefix}/show/{self.req.pk}/").content.decode()
            self.assertIn(expected, page, prefix)
            self.assertNotIn("552744", page, prefix)
            self.assertNotIn("+00:00", page, prefix)


class ReadOnlyPreviewTests(LifecycleFixtures):
    PREFIXES = ("", "/kz", "/en")

    def test_preview_does_not_change_status_and_offers_send(self):
        a = self._mk()
        self.client.force_login(self.op_user)
        for prefix in self.PREFIXES:
            with self.subTest(prefix=prefix):
                for method in ("get", "post"):
                    response = getattr(self.client, method)(f"{prefix}/preview/{self.req.pk}/")
                    self.assertEqual(response.status_code, 200)
                    self.assertTrue(response.context["preview"])
                    page = response.content.decode()
                    self.assertIn(f'action="{prefix}/send/{self.req.pk}/"', page)
                    self.assertIn(f'href="{prefix}/show/{self.req.pk}/"', page)
                    # В предпросмотре нельзя добавить, удалить или править.
                    self.assertNotIn(f"{prefix}/add_attendee/", page)
                    self.assertNotIn("delete_attendee", page)
                    self.assertNotIn(f"/update_attendee/{a.pk}/", page)
                self.req.refresh_from_db()
                self.assertEqual(self.req.status, "Active")

    def test_regular_page_offers_preview_link_not_send(self):
        self._mk()
        self.client.force_login(self.op_user)
        for prefix in self.PREFIXES:
            with self.subTest(prefix=prefix):
                page = self.client.get(f"{prefix}/show/{self.req.pk}/").content.decode()
                self.assertIn(f'href="{prefix}/preview/{self.req.pk}/"', page)
                self.assertIn(f'href="{prefix}/add_attendee/{self.req.pk}/"', page)
                self.assertNotIn(f"{prefix}/send/", page)

    def test_sent_request_cannot_be_reopened_by_preview_or_back_to_change(self):
        self._mk(status="submitted")
        Request.objects.filter(pk=self.req.pk).update(status="Sent")
        self.client.force_login(self.op_user)
        for prefix in self.PREFIXES:
            with self.subTest(prefix=prefix):
                response = self.client.get(f"{prefix}/preview/{self.req.pk}/")
                self.assertRedirects(response, f"{prefix}/show/{self.req.pk}/", fetch_redirect_response=False)
                response = self.client.post(f"{prefix}/back_to_change/{self.req.pk}/")
                self.assertRedirects(response, f"{prefix}/show/{self.req.pk}/", fetch_redirect_response=False)
                self.req.refresh_from_db()
                self.assertEqual(self.req.status, "Sent")
                self.assertEqual(self.client.get(f"{prefix}/add_attendee/{self.req.pk}/").status_code, 409)

    def test_legacy_checking_request_works_like_active(self):
        self._mk()
        Request.objects.filter(pk=self.req.pk).update(status="Checking")
        self.client.force_login(self.op_user)
        page = self.client.get(f"/show/{self.req.pk}/").content.decode()
        self.assertIn(f'href="/preview/{self.req.pk}/"', page)
        self.assertIn(f'href="/add_attendee/{self.req.pk}/"', page)
        self.client.post(f"/back_to_change/{self.req.pk}/")
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "Active")

    def test_preview_of_foreign_request_is_refused(self):
        stranger = User.objects.create_user("stranger", password="x")
        Operator.objects.create(user=stranger, role="operator", patronymic="Н", phone_number="+70000000003")
        self.client.force_login(stranger)
        for prefix in self.PREFIXES:
            with self.subTest(prefix=prefix):
                response = self.client.get(f"{prefix}/preview/{self.req.pk}/")
                self.assertIn(response.status_code, (403, 404))


class StaffPagesReferenceTests(LifecycleFixtures):
    """Этап D: очередь проверки и дашборд на утверждённом эталоне (отчёт 19)."""

    def setUp(self):
        super().setUp()
        self.member = self._mk()
        self._send()
        self.client.force_login(self.super_user)

    def pages(self):
        return {
            "review": self.client.get(f"/review/{self.event.pk}/").content.decode(),
            "dashboard": self.client.get(f"/dashboard/{self.event.pk}/").content.decode(),
        }

    def test_shared_stylesheet_no_inline_styles_no_codes_or_emoji(self):
        import re

        for name, page in self.pages().items():
            with self.subTest(page=name):
                self.assertIn("/static/css/ds.css", page)
                self.assertNotIn("<style", page)
                self.assertNotIn("(ready)", page)
                self.assertNotIn("(draft)", page)
                self.assertIsNone(re.search("[\u2705\U0001F504\u270F\U0001F4E6\U0001F6A9\U0001F4E4\U0001F5C2]", page))
                self.assertIn('href="#content"', page)

    def test_navigation_marks_current_section(self):
        pages = self.pages()
        self.assertIn(f'href="/review/{self.event.pk}/" aria-current="page"', pages["review"])
        self.assertIn(f'href="/dashboard/{self.event.pk}/" aria-current="page"', pages["dashboard"])
        self.assertNotIn(f'href="/dashboard/{self.event.pk}/" aria-current="page"', pages["review"])

    def test_return_is_a_real_disclosure_button_with_labelled_reason(self):
        self._decide(self.member, "start")
        page = self.client.get(f"/review/{self.event.pk}/").content.decode()
        self.assertIn('<summary class="ds-btn ds-btn-danger">Вернуть оператору…</summary>', page)
        self.assertNotIn('role="button"', page)
        self.assertIn(f'<label class="ds-label" for="reason-{self.member.pk}">', page)
        self.assertIn(f'aria-describedby="reason-hint-{self.member.pk}"', page)

    def test_dashboard_review_count_opens_queue(self):
        page = self.pages()["dashboard"]
        self.assertRegex(page, rf'<a class="ds-stat" href="/review/{self.event.pk}/">\s*<span class="ds-stat-num">1</span>')
