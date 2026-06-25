"""P0-3: a single ``REDIS_URL`` must drive cache + celery so a managed-Redis host/auth
is honoured instead of silently falling back to the hardcoded ``redis://redis:6379/*``.

``redis_url_for_db`` derives a per-logical-db connection string from a base Redis URL
while preserving scheme, auth, host and port.
"""
from django.test import SimpleTestCase

from eventproject.redis_config import redis_url_for_db


class RedisUrlForDbTests(SimpleTestCase):
    def test_swaps_db_index(self):
        self.assertEqual(redis_url_for_db("redis://redis:6379/0", 1), "redis://redis:6379/1")

    def test_appends_db_when_absent(self):
        self.assertEqual(redis_url_for_db("redis://redis:6379", 1), "redis://redis:6379/1")

    def test_keeps_same_db(self):
        self.assertEqual(redis_url_for_db("redis://redis:6379/0", 0), "redis://redis:6379/0")

    def test_preserves_auth_host_port(self):
        self.assertEqual(
            redis_url_for_db("redis://:secret@cache.example:6380/0", 0),
            "redis://:secret@cache.example:6380/0",
        )

    def test_swaps_db_on_managed_url(self):
        self.assertEqual(
            redis_url_for_db("redis://:secret@cache.example:6380/0", 2),
            "redis://:secret@cache.example:6380/2",
        )

    def test_preserves_rediss_scheme(self):
        self.assertEqual(
            redis_url_for_db("rediss://user:pw@managed-host:6380/0", 1),
            "rediss://user:pw@managed-host:6380/1",
        )
