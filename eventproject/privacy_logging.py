import logging


_STANDARD_FIELDS = frozenset(logging.makeLogRecord({}).__dict__)


class HttpPrivacyFilter(logging.Filter):
    """Keep status diagnostics from framework and HTTP-client log records."""

    def filter(self, record):
        sources = ("django.request", "django.server", "django.security", "httpx", "httpcore")
        if not any(record.name == source or record.name.startswith(source + ".") for source in sources):
            return True
        status = getattr(record, "status_code", None)
        record.msg = "HTTP response status=%d" % status if isinstance(status, int) else "HTTP transport event"
        record.args = ()
        record.exc_info = record.exc_text = record.stack_info = None
        # Structured formatters also serialize arbitrary record extras.
        allowed = set(_STANDARD_FIELDS) | {"status_code"}
        for key in record.__dict__.keys() - allowed:
            del record.__dict__[key]
        return True
