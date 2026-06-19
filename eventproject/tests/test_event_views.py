from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from eventproject.models import Event, Operator, Category, Attendee, Request

class EventViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        
        # Superoperator
        self.sop_user = User.objects.create_user("sop_user", password="pass")
        self.sop = Operator.objects.create(
            user=self.sop_user,
            patronymic="Sop",
            phone_number="+70000000001",
            workplace="HQ",
            role="superoperator",
        )
        
        # Operator
        self.op_user = User.objects.create_user("op_user", password="pass")
        self.op = Operator.objects.create(
            user=self.op_user,
            patronymic="Op",
            phone_number="+70000000002",
            workplace="HQ",
            role="operator",
        )
        
        # Initial event
        self.event = Event.objects.create(
            title="Initial Event",
            start_date="2026-05-01",
            end_date="2026-05-03",
            name_rus="Initial Event Legacy",
            date_start="2026-05-01",
            date_end="2026-05-03"
        )
        # Assign event to operator
        self.op.events.add(self.event)

    def test_superoperator_can_create_event(self):
        self.client.force_authenticate(user=self.sop_user)
        data = {
            "title": "New Event",
            "start_date": "2026-06-01",
            "end_date": "2026-06-03",
            "description": "Some description"
        }
        response = self.client.post("/api/v1/events/", data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Event.objects.filter(title="New Event").count(), 1)
        event = Event.objects.get(title="New Event")
        self.assertEqual(event.created_by, self.sop_user)

    def test_operator_cannot_create_event(self):
        self.client.force_authenticate(user=self.op_user)
        data = {"title": "Illegal Event"}
        response = self.client.post("/api/v1/events/", data)
        self.assertEqual(response.status_code, 403)

    def test_superoperator_can_add_category(self):
        self.client.force_authenticate(user=self.sop_user)
        data = {"name": "VIP Category"}
        response = self.client.post(f"/api/v1/events/{self.event.id}/categories/", data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Category.objects.filter(name="VIP Category", event=self.event).count(), 1)

    def test_event_list_includes_attendee_count(self):
        # Create category and attendee
        cat = Category.objects.create(event=self.event, name="Staff")
        # Need a Request for attendee (legacy)
        req = Request.objects.create(
            name="TestBatch", 
            event=self.event, 
            status="Active", 
            created_by=self.sop,
            registration_time="2026-04-18T12:00:00Z"
        )
        Attendee.objects.create(
            surname="Doe", 
            firstname="John", 
            request=req, 
            category=cat,
            dateAdd="2026-04-18T12:00:00Z",
            visitObjects="Gate 1",
            docIssue="Police"
        )
        
        self.client.force_authenticate(user=self.sop_user)
        response = self.client.get("/api/v1/events/")
        self.assertEqual(response.status_code, 200)
        
        # No pagination configured by default, returns list
        results = response.json()
        event_data = next(e for e in results if e["id"] == self.event.id)
        cat_data = next(c for c in event_data["categories"] if c["name"] == "Staff")
        self.assertEqual(cat_data["attendee_count"], 1)

    def test_operator_cannot_read_other_event_categories(self):
        # Other event NOT assigned to operator
        other_event = Event.objects.create(
            title="Secret Event", 
            start_date="2026-07-01", 
            end_date="2026-07-03",
            name_rus="Secret Event Legacy",
            date_start="2026-07-01",
            date_end="2026-07-03"
        )
        
        self.client.force_authenticate(user=self.op_user)
        # 403 is returned because IsSuperoperator permission blocks operators
        response = self.client.get(f"/api/v1/events/{other_event.id}/categories/")
        self.assertEqual(response.status_code, 403)
