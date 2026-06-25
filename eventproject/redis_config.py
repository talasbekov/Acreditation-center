"""Helpers for deriving per-logical-db Redis connection strings from one base URL.

Compose injects a single ``REDIS_URL`` (host/port/auth). Settings need distinct logical
databases (cache vs celery broker/result); this keeps them all anchored to that one base
so a managed-Redis host or password is honoured everywhere instead of silently falling
back to a hardcoded ``redis://redis:6379/*``.
"""
from urllib.parse import urlsplit, urlunsplit


def redis_url_for_db(base_url: str, db: int) -> str:
    """Return ``base_url`` with its path replaced by ``/<db>``.

    Scheme (``redis``/``rediss``), userinfo (auth), host and port are preserved; any
    query/fragment is dropped (Redis connection URLs do not use them for the db index).
    """
    parts = urlsplit(base_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{db}", "", ""))
