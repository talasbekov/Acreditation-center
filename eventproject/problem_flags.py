"""Story fe-3.1 — закрытый enum проблемных флагов заявки + вычисление.

Чистый модуль (минимум зависимостей) — контракт очереди проверки (fe-3.1 AC-2):
`problem_flags` в DTO — подмножество ЗАКРЫТОГО набора `PROBLEM_FLAGS`. Значение вне
набора невозможно по построению (тест перебирает enum). Флаги хранятся в
`Attendee.problem_flags` (JSONField) и популируются при submit через
`compute_problem_flags` — чтобы `?problem=`-фильтр работал с серверной пагинацией.

Какие члены набора вычисляются при submit (надёжно, без I/O по картинкам и без
декрипта чужих строк):
  • no_photo — `not attendee.photo` (фото опционально → достижимо в норме).

Остальные члены ЗАРЕЗЕРВИРОВАНЫ в наборе (контракт), но при submit НЕ вычисляются:
  • iin_invalid / duplicate_attendee — мертвы на submit-пути: `resolve_residency`
    отвергает невалидный ИИН резидента ДО перехода, а дубликат блокируется на create;
    плюс надёжная проверка дубликата требовала бы декрипта ВСЕХ ИИН события (одна
    битая ciphertext → 500 при submit несвязанной валидной заявки; O(N) перф).
  • photo_ratio / doc_unreadable — единственный источник (Pillow при загрузке)
    отклоняет плохой файл ДО сохранения → пост-фактум-сигнал не персистится.
Их популяция (из сохранённого upload-сигнала / legacy-импорта) — follow-up. Все члены
представимы в DTO/фильтре (тест перебирает набор).
"""


class ProblemFlag:
    NO_PHOTO = "no_photo"
    DOC_UNREADABLE = "doc_unreadable"
    PHOTO_RATIO = "photo_ratio"
    DUPLICATE_ATTENDEE = "duplicate_attendee"
    IIN_INVALID = "iin_invalid"


# Закрытый набор (детерминированный порядок). Источник правды для DTO/zod/фильтра.
PROBLEM_FLAGS = (
    ProblemFlag.NO_PHOTO,
    ProblemFlag.DOC_UNREADABLE,
    ProblemFlag.PHOTO_RATIO,
    ProblemFlag.DUPLICATE_ATTENDEE,
    ProblemFlag.IIN_INVALID,
)

_PROBLEM_FLAG_SET = frozenset(PROBLEM_FLAGS)


def is_valid_problem_flag(value) -> bool:
    """True, если value — член закрытого набора (для валидации `?problem=` и DTO-фильтра)."""
    return value in _PROBLEM_FLAG_SET


def sanitize_problem_flags(values) -> list:
    """Оставляет только валидные члены набора, в детерминированном порядке PROBLEM_FLAGS.

    Защита DTO: битое/legacy-значение в хранимом JSONField не должно протечь наружу
    (иначе zod-схема фронта отвергла бы ВЕСЬ ответ — one-bad-row outage страницы).
    """
    present = set(values or [])
    return [f for f in PROBLEM_FLAGS if f in present]


def compute_problem_flags(attendee) -> list:
    """Подмножество PROBLEM_FLAGS для заявки при submit (см. docstring модуля).

    Вычисляет только надёжное-и-достижимое без декрипта чужих строк: `no_photo`.
    Детерминированный порядок по PROBLEM_FLAGS.
    """
    flags = []
    if not attendee.photo:
        flags.append(ProblemFlag.NO_PHOTO)
    return [f for f in PROBLEM_FLAGS if f in flags]
