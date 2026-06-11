import logging


class StructuredContextFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, "user_id"):
            record.user_id = None
        if not hasattr(record, "role"):
            record.role = None
        if not hasattr(record, "action"):
            record.action = None
        if not hasattr(record, "obj_type"):
            record.obj_type = None
        if not hasattr(record, "obj_id"):
            record.obj_id = None
        if not hasattr(record, "ip"):
            record.ip = None
        return True
