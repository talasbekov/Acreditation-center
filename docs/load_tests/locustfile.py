# docs/load_tests/locustfile.py
import random
import os
from locust import HttpUser, task, between, events

# Default request_id for testing. Adjust if needed.
TEST_REQUEST_ID = os.environ.get("TEST_REQUEST_ID", "1")
TEST_USER = os.environ.get("TEST_USER", "load_test_user")
TEST_PASS = os.environ.get("TEST_PASS", "load_test_pass")

# IDs from DB preparation
SEX_ID = "1"
COUNTRY_ID = "1"
DOCTYPE_ID = "1"


class AttendeeUser(HttpUser):
    """Simulates an operator viewing the list and adding attendees."""

    wait_time = between(1, 3)

    def on_start(self):
        """Authentication via Django session."""
        # Get CSRF token from login page
        response = self.client.get("/user_login/")
        csrftoken = response.cookies.get("csrftoken", "")
        
        # Login
        self.client.post(
            "/user_login/",
            data={
                "username": TEST_USER,
                "password": TEST_PASS,
                "csrfmiddlewaretoken": csrftoken,
            },
            headers={"Referer": self.host + "/user_login/"},
        )

    @task(5)
    def health_check(self):
        """Simple health check - high frequency."""
        self.client.get("/health/", name="/health/")

    @task(3)
    def api_health_check(self):
        """API health check with DB connectivity check."""
        self.client.get("/api/health/", name="/api/health/")

    @task(2)
    def view_dashboard(self):
        """View main application dashboard."""
        self.client.get("/application/", name="/dashboard/")

    @task(1)
    def add_attendee(self):
        """Add an attendee - heaviest scenario."""
        # First get the form to get CSRF token
        response = self.client.get(f"/add_attendee/{TEST_REQUEST_ID}/")
        if response.status_code == 200:
            csrftoken = response.cookies.get("csrftoken", "")
            
            # Prepare dummy files for multipart
            photo_content = b"fake-photo-content" * 1000  # ~18KB
            doc_content = b"fake-doc-content" * 1000      # ~16KB
            
            files = {
                "photo": ("photo.jpg", photo_content, "image/jpeg"),
                "doc_photo": ("doc.jpg", doc_content, "image/jpeg"),
            }
            
            data = {
                "req_id": TEST_REQUEST_ID,
                "last_name": f"TestLoad_{random.randint(1, 999999)}",
                "first_name": "Load",
                "patronymic": "Testing",
                "latin_name": "Load Testing",
                "iin": "".join([str(random.randint(0, 9)) for _ in range(12)]),
                "dob": "1990-01-01",
                "sex": SEX_ID,
                "citizenship": COUNTRY_ID,
                "post": "Tester",
                "document_type": DOCTYPE_ID,
                "doc_series": "N",
                "doc_number": str(random.randint(10000000, 99999999)),
                "doc_date_start": "2020-01-01",
                "doc_date_end": "2030-01-01",
                "doc_issuer": "MVD",
                "visit_objects": "All",
                "category": "A",
                "csrfmiddlewaretoken": csrftoken,
            }
            
            self.client.post(
                f"/add_attendee/{TEST_REQUEST_ID}/",
                data=data,
                files=files,
                headers={"Referer": self.host + f"/add_attendee/{TEST_REQUEST_ID}/"},
                name="/add_attendee/",
            )
