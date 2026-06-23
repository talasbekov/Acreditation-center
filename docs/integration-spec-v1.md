# Integration Spec v1.0 — формат экспорта участников (downstream security-система)

> **СТАТУС: `DRAFT` — UNCONFIRMED.**
> Поля и форматы ниже выведены из модели `Attendee` и являются **предположением**.
> Они подлежат подтверждению downstream-системой через Project Lead (Erda) до перевода
> Story 4.1 в `done` и до старта Story 4.3. См. раздел «Открытые вопросы».
>
> Машиночитаемый источник правды: [`integration-spec-v1.schema.json`](./integration-spec-v1.schema.json)
> (его проверяет `eventproject/tests/test_export_contract.py`).

**Версия:** 1.0-DRAFT · **Дата:** 2026-06-23 · **Story:** 4.1

## Назначение

Контракт формата выгрузки участников в downstream security-систему. Export serializer
(Story 4.3) и contract-тест ссылаются на **эту спеку как единственный источник** — поля не
дублируются «на глаз». Цель — приём каждой выгруженной записи downstream с первого раза.

## Структура архива

ZIP: `export_<event_id>_<category>_<timestamp>.zip`
```
export_5_Охрана_20260623T100000Z.zip
├── attendees.json          # массив объектов attendee (формат ниже)
├── photos/
│   └── <attendee_id>.jpg    # фото участника
└── documents/
    └── <attendee_id>.jpg    # скан документа
```
Имена медиафайлов в архиве соответствуют `attendee_id` из JSON.

## Объект `attendee` (элемент `attendees.json`)

| Поле JSON | Тип | Обяз. | Null | Источник (`Attendee.*`) |
|---|---|---|---|---|
| `attendee_id` | integer | ✓ | — | `id` |
| `event_id` | integer | ✓ | — | `request.event.id` |
| `event_code` | string | ✓ | — | `request.event.event_code` |
| `category` | string | ✓ | да | `category.name` |
| `status` | string (`ready`) | ✓ | — | `status` (экспортируются только `ready`) |
| `surname` | string | ✓ | — | `surname` |
| `firstname` | string | ✓ | — | `firstname` |
| `patronymic` | string | — | да | `patronymic` |
| `transcription` | string (latin) | ✓ | — | `transcription` |
| `birth_date` | date `YYYY-MM-DD` | ✓ | да | `birthDate` |
| `iin` | string `^[0-9]{12}$` | ✓ | да | `iin` (расшифрован; null для нерезидента) — **PII** |
| `is_resident` | boolean | ✓ | — | `is_resident` |
| `sex_id` | string | ✓ | — | `sexId` (id `directories.Sex`) |
| `country_id` | string | ✓ | — | `countryId` (id `directories.Country`) |
| `post` | string | ✓ | — | `post` |
| `doc_type_id` | string | ✓ | — | `docTypeId` (id `directories.DocumentType`) |
| `doc_series` | string | ✓ | — | `docSeries` |
| `doc_number` | string | — | да | `docNumber` |
| `doc_begin` | date `YYYY-MM-DD` | — | да | `docBegin` |
| `doc_end` | date `YYYY-MM-DD` | — | да | `docEnd` |
| `doc_issue` | string | ✓ | — | `docIssue` |
| `visit_objects` | string | ✓ | — | `visitObjects` |
| `date_add` | datetime ISO8601 | ✓ | — | `dateAdd` |
| `photo_file` | string `photos/…` | ✓ | — | путь в ZIP |
| `doc_scan_file` | string `documents/…` | ✓ | — | путь в ZIP |

### Форматы значений (DRAFT-допущения)
- **Даты:** ISO `YYYY-MM-DD`. **datetime:** ISO8601 с TZ (`2026-06-23T10:00:00+00:00`).
- **Строки:** UTF-8. **Булевы:** JSON `true`/`false`.
- **null:** отсутствующее опциональное значение передаётся как JSON `null`.

### Пример валидного объекта
```json
{
  "attendee_id": 123,
  "event_id": 5,
  "event_code": "T1",
  "category": "Охрана",
  "status": "ready",
  "surname": "Иванов",
  "firstname": "Иван",
  "patronymic": "Петрович",
  "transcription": "Ivanov Ivan",
  "birth_date": "1990-01-01",
  "iin": "900101300007",
  "is_resident": true,
  "sex_id": "M",
  "country_id": "1000000105",
  "post": "Инженер",
  "doc_type_id": "passport",
  "doc_series": "AA",
  "doc_number": "123456",
  "doc_begin": "2020-01-01",
  "doc_end": "2030-01-01",
  "doc_issue": "МВД",
  "visit_objects": "Объект A",
  "date_add": "2026-06-23T10:00:00+00:00",
  "photo_file": "photos/123.jpg",
  "doc_scan_file": "documents/123.jpg"
}
```

## Открытые вопросы (требуют подтверждения downstream / Erda)

1. **🔴 Полный список полей и их форматы** — подтвердить/скорректировать таблицу выше реальными требованиями downstream.
2. **ИИН в экспорте** — нужен ли расшифрованный ИИН (PII)? Если да — согласовать защиту канала передачи.
3. **Справочники** (`country_id`/`sex_id`/`doc_type_id`) — отдавать ID (как сейчас) или человекочитаемое имя (рус/каз/англ)?
4. **Формат дат** — `YYYY-MM-DD` или `DD.MM.YYYY`? datetime — ISO8601?
5. **Медиа** — подтвердить отдельные файлы в `photos/`/`documents/` (vs base64-инлайн); допустимые форматы/макс. размер.
6. **Идентификатор** записи — `attendee_id` (PK) или иной бизнес-ключ для связи JSON↔файлы?

## Политика версионирования (AC-5)

При изменении требований downstream: обновить этот документ **и** `integration-spec-v1.schema.json`,
обновить `test_export_contract.py`, поднять версию (`1.0` → `1.1`/`2.0`) и добавить запись в историю.

## История версий
- **1.0-DRAFT (2026-06-23):** первичный черновик из модели `Attendee` (Story 4.1). Не подтверждён downstream.
