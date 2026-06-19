from django.test import TestCase
from django.contrib.auth.models import User
from eventproject.models import Event, Category

class EventModelTest(TestCase):
    def test_create_event_with_new_fields(self):
        user = User.objects.create_user(username="testuser")
        event = Event.objects.create(
            title="Test Event",
            description="Test Description",
            start_date="2026-05-01",
            end_date="2026-05-03",
            created_by=user,
            # Legacy fields
            name_rus="Legacy Name",
            date_start="2026-05-01",
            date_end="2026-05-03"
        )
        self.assertEqual(event.title, "Test Event")
        self.assertEqual(event.created_by, user)

    def test_create_category(self):
        event = Event.objects.create(
            title="Test Event", 
            start_date="2026-05-01", 
            end_date="2026-05-03",
            # Legacy fields
            name_rus="Legacy Name",
            date_start="2026-05-01",
            date_end="2026-05-03"
        )
        category = Category.objects.create(event=event, name="VIP")
        self.assertEqual(category.name, "VIP")
        self.assertEqual(category.event, event)
