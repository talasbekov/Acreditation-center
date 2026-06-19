import importlib
from importlib import import_module

from datetime import date

from django.contrib.auth.models import User
from django.core.exceptions import FieldError, ImproperlyConfigured
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase
from django.test import SimpleTestCase
from django.test import TransactionTestCase
from django.test.utils import override_settings
from django.utils import timezone

from eventproject.models import Attendee, Event, Operator, Request
from eventproject.views import check_dublicate


class EncryptionConfigurationTests(SimpleTestCase):
    def test_env_example_contains_fernet_placeholder(self):
        with open(".env.example", encoding="utf-8") as env_example:
            contents = env_example.read()

        self.assertIn("FERNET_KEYS=your-fernet-key-here", contents)

    def test_settings_expose_fernet_keys(self):
        import eventproject.settings_test as settings_test

        reloaded = importlib.reload(settings_test)

        self.assertTrue(hasattr(reloaded, "FERNET_KEYS"))
        self.assertIsInstance(reloaded.FERNET_KEYS, list)
        self.assertEqual(len(reloaded.FERNET_KEYS), 1)
        self.assertTrue(reloaded.FERNET_KEYS[0])


class EncryptionModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="enc-user", password="secret")
        cls.operator = Operator.objects.create(
            user=cls.user,
            patronymic="Test",
            phone_number="+70000000000",
            workplace="Test Workplace",
        )
        cls.event = Event.objects.create(
            name_rus="Test Event",
            name_kaz="Test Event",
            name_eng="Test Event",
            event_code="ENC",
            date_start=date.today(),
            date_end=date.today(),
            city_code="AK",
        )
        cls.request = Request.objects.create(
            name="Encryption Request",
            event=cls.event,
            status="Active",
            created_by=cls.operator,
            registration_time=timezone.now(),
        )

    def _create_attendee(self, iin="123456789012"):
        return Attendee.objects.create(
            surname="Doe",
            firstname="Jane",
            patronymic="Test",
            transcription="Jane Doe",
            iin=iin,
            birthDate=date(1990, 1, 1),
            post="Engineer",
            countryId="1000000105",
            docTypeId="passport",
            docSeries="AA",
            docNumber="123456",
            docBegin=date(2020, 1, 1),
            docEnd=date(2030, 1, 1),
            docIssue="Issuer",
            sexId="M",
            dateAdd=timezone.now(),
            visitObjects="Object",
            request=self.request,
            dateEnd=date.today(),
            stickId="CAT",
        )

    def test_new_iin_is_not_stored_as_plaintext(self):
        attendee = self._create_attendee()

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT iin FROM eventproject_attendee WHERE id = %s", [attendee.pk]
            )
            stored_value = cursor.fetchone()[0]

        self.assertNotEqual(stored_value, "123456789012")

    def test_direct_filter_by_iin_is_not_supported(self):
        self._create_attendee()

        with self.assertRaises(FieldError):
            Attendee.objects.filter(iin="123456789012").exists()

    def test_duplicate_check_still_works_for_encrypted_iin(self):
        existing = self._create_attendee()
        candidate = Attendee(
            surname="Other",
            firstname="Person",
            patronymic="Test",
            transcription="Other Person",
            iin=existing.iin,
            birthDate=date(1991, 1, 1),
            post="Engineer",
            countryId="1000000105",
            docTypeId="passport",
            docSeries="BB",
            docNumber="654321",
            docBegin=date(2020, 1, 1),
            docEnd=date(2030, 1, 1),
            docIssue="Issuer",
            sexId="M",
            dateAdd=timezone.now(),
            visitObjects="Object",
            request=self.request,
            dateEnd=date.today(),
            stickId="CAT",
        )

        self.assertTrue(check_dublicate(candidate, self.request))


class EncryptionMigrationTests(TransactionTestCase):
    reset_sequences = True
    migrate_from = ("eventproject", "0008_alter_attendee_docissue_alter_attendee_docnumber_and_more")
    migrate_to = ("eventproject", "0010_swap_attendee_iin_encrypted")

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.loader.build_graph()
        self.executor.migrate([self.migrate_from])
        self.old_apps = self.executor.loader.project_state([self.migrate_from]).apps

    def tearDown(self):
        self.executor = MigrationExecutor(connection)
        self.executor.loader.build_graph()
        # Migrate to the latest leaf migrations so subsequent TransactionTestCase
        # tests see a fully-migrated schema (not just up to migrate_to).
        latest = self.executor.loader.graph.leaf_nodes()
        self.executor.migrate(latest)
        super().tearDown()

    def _create_plaintext_attendee(self, iin="123456789012"):
        user = self.old_apps.get_model("auth", "User").objects.create(username=f"user-{iin or 'null'}")
        operator = self.old_apps.get_model("eventproject", "Operator").objects.create(
            user=user,
            patronymic="Test",
            phone_number="+70000000000",
            workplace="Test Workplace",
        )
        event = self.old_apps.get_model("eventproject", "Event").objects.create(
            name_rus="Test Event",
            name_kaz="Test Event",
            name_eng="Test Event",
            event_code=f"E{user.pk}",
            date_start=date.today(),
            date_end=date.today(),
            city_code="AK",
        )
        request = self.old_apps.get_model("eventproject", "Request").objects.create(
            name=f"Request {user.pk}",
            event=event,
            status="Active",
            created_by=operator,
            registration_time=timezone.now(),
        )
        attendee = self.old_apps.get_model("eventproject", "Attendee").objects.create(
            surname="Doe",
            firstname="Jane",
            patronymic="Test",
            transcription="Jane Doe",
            iin=iin,
            birthDate=date(1990, 1, 1),
            post="Engineer",
            countryId="1000000105",
            docTypeId="passport",
            docSeries="AA",
            docNumber="123456",
            docBegin=date(2020, 1, 1),
            docEnd=date(2030, 1, 1),
            docIssue="Issuer",
            sexId="M",
            dateAdd=timezone.now(),
            visitObjects="Object",
            request=request,
            dateEnd=date.today(),
            stickId="CAT",
        )
        return attendee.pk

    def _migrate_forward(self):
        self.executor = MigrationExecutor(connection)
        self.executor.loader.build_graph()
        self.executor.migrate([self.migrate_to])
        return self.executor.loader.project_state([self.migrate_to]).apps

    def _migrate_backward(self):
        self.executor = MigrationExecutor(connection)
        self.executor.loader.build_graph()
        self.executor.migrate([self.migrate_from])
        return self.executor.loader.project_state([self.migrate_from]).apps

    def test_data_migration_encrypts_existing_iin_and_preserves_orm_reads(self):
        attendee_pk = self._create_plaintext_attendee()

        apps = self._migrate_forward()
        attendee = apps.get_model("eventproject", "Attendee").objects.get(pk=attendee_pk)

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT iin FROM eventproject_attendee WHERE id = %s", [attendee_pk]
            )
            stored_value = cursor.fetchone()[0]

        self.assertEqual(attendee.iin, "123456789012")
        self.assertNotEqual(stored_value, "123456789012")

    def test_null_iin_remains_null_after_migration(self):
        attendee_pk = self._create_plaintext_attendee(iin=None)

        apps = self._migrate_forward()
        attendee = apps.get_model("eventproject", "Attendee").objects.get(pk=attendee_pk)

        self.assertIsNone(attendee.iin)

    def test_backward_migration_restores_plaintext_iin(self):
        attendee_pk = self._create_plaintext_attendee()

        self._migrate_forward()
        self._migrate_backward()

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT iin FROM eventproject_attendee WHERE id = %s", [attendee_pk]
            )
            stored_value = cursor.fetchone()[0]

        self.assertEqual(stored_value, "123456789012")

    def test_batch_migration_handles_150_attendees(self):
        attendee_ids = [self._create_plaintext_attendee(iin=f"{i:012d}") for i in range(150)]

        apps = self._migrate_forward()
        AttendeeModel = apps.get_model("eventproject", "Attendee")

        self.assertEqual(AttendeeModel.objects.count(), 150)

        migrated = AttendeeModel.objects.filter(pk__in=attendee_ids).order_by("pk")
        self.assertEqual(sum(1 for attendee in migrated if attendee.iin is not None), 150)

    @override_settings(FERNET_KEYS=[])
    def test_missing_fernet_keys_raise_improperly_configured(self):
        migration = import_module("eventproject.migrations.0009_attendee_iin_encrypted")

        with self.assertRaises(ImproperlyConfigured):
            migration._ensure_fernet_keys()

    def test_encryption_migration_rolls_back_on_mid_batch_failure(self):
        first_pk = self._create_plaintext_attendee(iin="123456789012")
        second_pk = self._create_plaintext_attendee(iin="123456789013")

        migration = import_module("eventproject.migrations.0009_attendee_iin_encrypted")
        add_field_operation = migration.Migration.operations[0]

        from_state = self.executor.loader.project_state([self.migrate_from])
        to_state = self.executor.loader.project_state(
            [("eventproject", "0009_attendee_iin_encrypted")]
        )

        with connection.schema_editor() as schema_editor:
            add_field_operation.database_forwards(
                "eventproject", schema_editor, from_state, to_state
            )

        apps = to_state.apps
        AttendeeModel = apps.get_model("eventproject", "Attendee")
        original_save = AttendeeModel.save
        save_counter = {"count": 0}

        def failing_save(instance, *args, **kwargs):
            save_counter["count"] += 1
            if save_counter["count"] == 2:
                raise RuntimeError("simulated migration failure")
            return original_save(instance, *args, **kwargs)

        AttendeeModel.save = failing_save
        try:
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    migration.encrypt_existing_iin(apps, None)
        finally:
            AttendeeModel.save = original_save

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT iin_encrypted FROM eventproject_attendee WHERE id IN (%s, %s) ORDER BY id",
                [first_pk, second_pk],
            )
            encrypted_values = [row[0] for row in cursor.fetchall()]

        self.assertEqual(encrypted_values, [None, None])

        with connection.schema_editor() as schema_editor:
            add_field_operation.database_backwards(
                "eventproject", schema_editor, to_state, from_state
            )
