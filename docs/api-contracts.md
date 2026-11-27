# API-контракты — eventproject

> Обновлено: 2026-06-11 (исчерпывающее сканирование).

## Аутентификация

- **HTML-интерфейс**: сессионная аутентификация Django (`login_required`), декоратор `superuser_required` для админ-операций.
- **DRF API** (`/api/v1/...`): `SessionAuthentication` (по умолчанию в `REST_FRAMEWORK`), permission-классы RBAC из `eventproject/permissions.py`. JWT (simplejwt) установлен, но не активирован.
- **Cookies**: `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`, `CSRF_COOKIE_SAMESITE='Strict'`. Таймаут сессии по ролям: superuser — 4 ч, оператор — 12 ч.

## Health-check

| URL | Метод | Auth | Ответ |
|-----|-------|------|-------|
| `/health/`, `/healthz/` | GET | — | `{"status": "ok"}` |
| `/api/health/` | GET | — | `{"status": "ok|error", "db": "ok|unreachable"}` (503 при недоступной БД) |

## DRF REST API (`eventproject/api/urls.py`)

DefaultRouter, базовый префикс `/api/v1/`. Ошибки — формат **RFC 7807** (`api/exceptions.py`): `{"type", "title", "detail", "field"}`.

| URL | Метод | ViewSet/функция | Permissions | Назначение |
|-----|-------|----------------|-------------|-----------|
| `/api/v1/events/` | GET | EventViewSet.list | IsSuperoperator | События пользователя (все — для superoperator/superuser, через `get_operator_events()`) |
| `/api/v1/events/` | POST | EventViewSet.create | IsSuperoperator | Создание события, `created_by=request.user` |
| `/api/v1/events/<id>/` | GET/PUT/DELETE | EventViewSet | IsSuperoperator | Чтение/обновление/удаление |
| `/api/v1/events/<id>/categories/` | GET/POST | action `categories` | IsSuperoperator | Категории события |
| `/api/v1/rbac-check/` | GET | `rbac_check` | IsAuthenticated | `{"role": "<роль>"}` |

**Участники (`/api/v1/attendees/`, этап C).** Карточка (`GET /<id>/`) отдаёт `review_comment` — причину возврата от проверяющего, только чтение. Строка списка отдаёт `returned` (черновик с причиной возврата), саму причину — нет. С этапа D строка списка отдаёт также `request_name` (номер заявки) и `event_name` (название мероприятия, `name_rus`), только чтение. Этап D, форма участника: `GET /api/v1/directories/` (оператор) — `{sexes, document_types, categories, countries}`, строки `{code, name}`. Сериализатор участника принимает `stickId` (у резидента РК сохраняется пустым), `docSeries` и `docIssue` необязательны; при создании проверяются даты (`docBegin` не в будущем, `docEnd` не в прошлом, `birthDate` не в будущем). Ответ 400 по полям дополнительно содержит `errors: {поле: текст}` (тексты по-русски); `field` и `detail` прежние. `POST /<id>/submit/` — черновик на проверку; если не хватает данных — 400, в `detail` недостающее перечислено словами («Участник не готов к отправке: нет фото, нет скана документа»); недопустимый переход — 409. Решения проверяющего — `start-review/`, `approve/`, `return/` (с `reason`).

**Сериализаторы**: `EventSerializer` (id, title, start_date, end_date, description, categories nested, created_at), `CategorySerializer` (id, name, attendee_count — вычисляемое `obj.attendees.count()`).

**Permission-классы**: `IsSuperuser` (только superuser), `IsSuperoperator` (superoperator+superuser), `IsOperator` (operator+superoperator+superuser).

## HTML-интерфейс (сессионный)

Три языковые версии: русский (корень), казахский (`/kz/...`), английский (`/en/...`). Обработчик у всех трёх один (`eventproject/views/`), язык передаётся из URL (`{"lang": "kz"}`); шаблоны общие: строки интерфейса — `{% t %}` со словарём `eventproject/ui_text.py`, тексты сообщений — `eventproject/page_lang.py`, справочники сортируются по `name_kaz`/`name_eng`. Форма правки участника — `/update_attendee/<id>/`, `/kz/update_attendee/<id>/`, `/en/update_attendee/<id>/`.

### Аутентификация и сессия

| URL | Метод | Auth | Назначение |
|-----|-------|------|-----------|
| `/`, `/user_login/` (+`/kz/`, `/en/`) | GET/POST | — | Вход; редирект superuser → `/avmac/`, оператор → `/application/` |
| `/logout/` (+kz/en) | GET | login | Выход |
| `/auth_check/` | GET | login | 200 для Nginx auth_request |
| `/change_password/` (+kz/en) | GET/POST | login | Смена пароля |

### Мероприятия и операторы (только superuser)

| URL | Метод | Назначение |
|-----|-------|-----------|
| `/avmac/` | GET | Админ-панель (все события, операторы, города) |
| `/create_event/` | POST | Создание мероприятия |
| `/show_event/<event_id>/` | GET | Детали мероприятия |
| `/delete_event/<event_id>/` | GET | Удаление мероприятия + медиа-папки `media/event_<id>` |
| `/flush_outdated_events/` | GET | Удаление мероприятий старше 900 дней + папки `output/` |
| `/add_operator/` | POST | Создание оператора (User+Operator, генерация пароля) |
| `/show_operator/<id>/` | GET | Карточка оператора |
| `/delete_operator/<username>/` | GET | Удаление оператора |
| `/new_password/<username>/` | GET | Новый пароль (`token_urlsafe(8)`) |
| `/add_operator_to_event/`, `/bind_operators/` | POST | Привязка операторов к мероприятию |
| `/unbind_event/<event_id>/<username>/` | GET | Отвязка |

### Заявки (операторы; + kz/en зеркала)

| URL | Метод | Назначение |
|-----|-------|-----------|
| `/application/` | GET | Кабинет оператора (его события и заявки) |
| `/create/<event_id>/` | GET/POST | Новая заявка (status=`Active`) |
| `/show/<request_id>/` | GET | Заявка со списком участников |
| `/show_request_to_admin/<request_id>/` | GET | Просмотр заявки админом (superuser) |
| `/preview/<request_id>/` | GET (POST — для страниц, открытых до обновления) | Предпросмотр перед отправкой, **только чтение**: статус не меняется; кнопки «Вернуться к редактированию» и «Отправить», без добавления, правки и удаления. Отправленная заявка → редирект на `/show/` |
| `/back_to_change/<request_id>/` | POST + CSRF | Снимает прежний статус `Checking` (→ `Active`) и ведёт на `/show/`; отправленную заявку не открывает |
| `/send/<request_id>/` | POST + CSRF | Все черновики → `submitted`, заявка → `Sent`, ставится `registration_time` (всё или ничего, этап C) |
| `/delete_request/<request_id>/` | GET | Удаление заявки с участниками |

### Участники (операторы; + kz/en зеркала)

| URL | Метод | Особенности |
|-----|-------|-------------|
| `/add_attendee/<request_id>/` | GET/POST | **@ratelimit(ip, 20/h, POST)** → 429. Валидация: даты документов/рождения, размер файлов 1KB–9MB, ИИН обязателен для граждан РК (countryId=1000000105), дубликаты по ИИН или ФИО+дата рождения. Аудит `attendee.create` |
| `/update_attendee/<attendee_id>/` | GET/POST | @ratelimit(20/h); смена метаданных без обязательной перезагрузки файлов. Аудит `attendee.update` |
| `/delete_attendee/` | POST | `attendee_id` в теле; если заявка пустеет — удаляется и заявка. Аудит `attendee.delete` |

### Экспорт (только superuser)

| URL | Метод | Назначение |
|-----|-------|-----------|
| `/download_json/<event_id>/` | GET | JSON участников (status=`Sent`), заявки → `Exported` |
| `/download_guests_json/<event_id>/` | GET | Аналогично |
| `/download_all_guests_json/<event_id>/` | GET | JSON (`Sent` + `Exported`) |
| `/download_request_json/<request_id>/` | GET | JSON одной заявки, → `Exported` |
| `/download_photos/<event_id>/` | GET | ZIP фото из `media/event_<id>/` (временный файл в `/tmp/`) |
| `/download_file/<event_id>/` | GET | Готовый `event_<id>.zip` (StreamingHttpResponse) |
| `/check_archive_status/<event_id>/` | GET | Статус из cache: `{'status': 'not_found'|'processing'|'completed', ...}` |

### Прочее

| URL | Назначение |
|-----|-----------|
| `/embankment/` | Django Admin |
| `/api/v1/public/content-manager/translations` | Mock — пустой `{}` |
| `/qr/` (GET/POST), `/qr/success/<pk>/` | QR-приложение: ввод ИИН (форма `QrIinForm`, 12 цифр) → генерация QR-PNG из `{"iin": <int>}` → страница успеха |

## Внешние интеграции

> **Важно**: интеграционные view (`kazenergy_receive`, `kazexpo_receive`) **не замаплены в urls.py**. Они вызываются изнутри по расписанию — `eventproject.cron.kazexpo_import_job` каждые 2 минуты (django-crontab, `CRONJOBS`) создаёт синтетический запрос через `RequestFactory` и `async_to_sync()`.

### Общий приём анкет партнёров (этап C, `services/partner_import.py`)

Оба партнёра обрабатываются одним циклом (не более `PARTNER_IMPORT_MAX_RECORDS`, по умолчанию 500 анкет за запуск):
1. GET очереди (`x-api-key`) — одна анкета за итерацию (`payload["attendees"][0]`); выход при пустом списке.
2. Анкета без `id` останавливает запуск: подтвердить её нельзя.
3. Анкета с уже известным `id` (таблица `PartnerReceipt`, уникальность источник + мероприятие + id) не обрабатывается заново — партнёру повторно уходит сохранённое подтверждение.
4. Новая анкета под блокировкой мероприятия: обязательные поля и даты → правило дублей (ИИН резидента / документ нерезидента) → проверка фото и скана по правилам API (JPEG/PNG/WEBP, ≤ 5 МБ до декодирования, 3×4, ≥ 600×800; скан может быть PDF) → запись черновика и квитанции. Неподходящий файл не сохраняется, анкета принимается без него с пометкой в подтверждении. Имя файла случайное.
5. Участник попадает в открытую (`Active`) заявку того же оператора за последний час, иначе создаётся новая; отправленные заявки не пополняются. Пустая очередь заявку не создаёт.
6. Подтверждение уходит только после записи. Если партнёр его не принял (не 2xx или сбой сети), запуск останавливается — при следующем запуске та же анкета получит то же подтверждение. Анкета, повторно выданная после успешного подтверждения, тоже останавливает запуск.

Итоговый ответ: `{"processed", "accepted", "duplicates", "errors", "request_id"}`; HTTP 200 при `errors == 0`, иначе 400; 502, если очередь недоступна и ничего не обработано.

### KazEnergy (`views/integration/integrate_kazenergy.py`)

Очередь `https://kazenergy.regist.kz/api/api.php`, подтверждение `POST …/ack.php`. Обязательные поля: surname, firstname, post, countryId, docTypeId, docNumber, sexId, visitObjects, transcription, dateAdd, birthDate, docBegin, docEnd. Коды: принято — `{"id", "code": 2}` (с `message`, если файл не принят); дубль — `code=2` (прежний контракт: очередь не возвращает анкету); отказ — `code=9` с `message`. Вызывается из `eventproject.cron.kazexpo_import_job` (Event 797, Operator 1405 заданы в коде).

### Avalon/KazExpo (`views/integration/integrate.py`)

POST супероператора/суперпользователя, назначенного на мероприятие; очередь и подтверждение — `https://avalon.kazintec.kz/api/v1/events/.../export`, 404/500 очереди завершают запуск, пауза 0.3 с. Обязательные поля: surname, firstname, post, countryId, docTypeId, sexId, visitObjects, transcription, birthDate, stickId. Коды: принято — `code=2` и `RECORD NUMBER` = `№<id участника>`; дубль — `code=1, comment="Дубликат"`; нет полей — `code=1` с перечнем; ошибка записи — `code=1, message="Ошибка при сохранении участника"`. CSV в `media/exports/` не пишется.

## Обработка ошибок и лимиты

- **429**: `handler429 = eventproject.views.ratelimited_error`; `RatelimitMiddleware` перехватывает `Ratelimited` глобально.
- **Брутфорс**: django-axes — 10 неудачных входов → блокировка IP на 1 час (`AXES_FAILURE_LIMIT=10`, `AXES_COOLOFF_TIME=1`, `AXES_RESET_ON_SUCCESS=True`, только `REMOTE_ADDR`).
- **Валидационные ошибки HTML-форм** возвращаются как HTTP 200 с сообщением в шаблоне (`gov3.html` / `request.html`).
- **DRF**: RFC 7807 problem details.
