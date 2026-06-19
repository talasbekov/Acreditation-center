def normalize_iin(value):
    if value is None:
        return None

    normalized = str(value).strip()
    return normalized or None


def mask_iin(value):
    """Маскирует ИИН для логов/экспортов: видны только последние 4 цифры."""
    normalized = normalize_iin(value)
    if not normalized:
        return ""
    return "********" + normalized[-4:]


def event_has_iin_duplicate(attendees, iin, exclude_pk=None):
    normalized_iin = normalize_iin(iin)
    if not normalized_iin:
        return False

    for attendee in attendees.only("pk", "iin"):
        if exclude_pk is not None and attendee.pk == exclude_pk:
            continue
        if normalize_iin(attendee.iin) == normalized_iin:
            return True

    return False
