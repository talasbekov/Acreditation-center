# Перевод интерфейса на Next.js (Django остаётся бэкендом)

**Решение от 28.11.2026.** Бэкенд — существующий Django (ветка `demo/all`: main + security-hardening + export/large-packages + return-reason + alpine). Интерфейс — Next.js из прототипа `accreditation.zip/frontend`. Go-мок из прототипа не используем; его `4.endpoints.md` служит только образцом экранов.

**Цель — паритет:** всё, что сейчас умеет старая АЦ (HTML-страницы, Django-админка, cron-импорт), доступно в новом интерфейсе и работает так же. Те же правила проверки, те же статусы, те же права. Функции, которых в старой АЦ нет (исполнение результата СГО, бейджи, саморегистрация, API-токены, доп. поля), идут вторым этапом.

## Архитектура

```
браузер ──► nginx ──┬── /            → Next.js (web/)
                    ├── /api/        → Django (DRF, сессия + CSRF)
                    ├── /media/      → Django protected_media
                    ├── /embankment/ → Django admin
                    └── старые HTML-маршруты → Django (пока новый UI не заменит их)
```

- **Авторизация:** Django-сессия, cookie `sessionid` + `csrftoken`. Next.js ходит на тот же origin; в dev — через `rewrites` в `next.config`. Токенов в `localStorage` нет.
- **Правила:** вся валидация, правила дубликатов, FSM статусов, шифрование ИИН и аудит остаются в Django (`services/intake.py`, `lifecycle.py`, `state_machine.py`, `audit.py`). API вызывает те же сервисы, что и HTML-вьюхи. Второй копии логики нет.
- **Языки:** RU/KZ/EN для всех экранов. Тексты берём из `ui_text.py`, чтобы формулировки совпадали со старыми.

## Карта: старая функция → API → экран

Обозначения: ✔ эндпоинт уже есть · ＋ добавить

### Вход и пароль
| Старое | API | Экран |
|---|---|---|
| `/`, `/user_login/`, `/kz/`, `/en/` | ＋ `POST /api/v1/auth/login/` (axes, `?next`, сообщение про деактивацию) | `/login` |
| `/logout/` | ＋ `POST /api/v1/auth/logout/` | шапка |
| — | ＋ `GET /api/v1/auth/me/` (роль, ФИО, `force_password_change`) | всё приложение |
| `/change_password/` + ForcePasswordChangeMiddleware | ＋ `POST /api/v1/auth/change-password/` | `/settings/password` |
| `/operator-access/<uid>/<token>/` | ＋ `GET`/`POST /api/v1/auth/operator-access/<uid>/<token>/` | `/operator-access/[uid]/[token]` |
| CSRF | ✔ `GET /api/v1/csrf/` | — |

### Админ: мероприятия
| Старое | API | Экран |
|---|---|---|
| `/avmac/`: список (≤900 дней), формы создания | ✔ `GET /api/v1/events/` + ＋ фильтр «актуальные» | `/events` |
| `/create_event/` | ✔ `POST /api/v1/events/` (проверить правила дат и обязательный RU) | диалог |
| `/show_event/<id>/` | ＋ `GET /api/v1/events/<id>/summary/` (операторы привязанные и нет, заявки по статусам, число невыгруженных, готовый ZIP) | `/events/[id]` |
| `/add_operator_to_event/`, `/bind_operators/` | ＋ `POST /api/v1/events/<id>/operators/` | вкладка «Операторы» |
| `/unbind_event/<event>/<username>/` | ＋ `DELETE /api/v1/events/<id>/operators/<op>/` | там же |
| `/delete_event/<id>/` (+ удаление media) | ＋ `DELETE /api/v1/events/<id>/` | карточка |
| категории мероприятия | ✔ `GET`/`POST /api/v1/events/<id>/categories/` | вкладка «Категории» |
| иерархия мероприятий (родитель/контейнер) | ✔ поля в EventSerializer | форма мероприятия |

### Админ: операторы
| Старое | API | Экран |
|---|---|---|
| `/add_operator/` | ✔ `POST /api/v1/operators/` | `/operators` |
| `/show_operator/<id>/` | ✔ `GET /api/v1/operators/<id>/` + ＋ его мероприятия и заявки | `/operators/[id]` |
| `/new_password/<username>/` | ✔ `resend_credentials` | карточка |
| деактивация / реактивация | ✔ `deactivate` / `reactivate` | карточка |
| `/delete_operator/<username>/` | ＋ `DELETE /api/v1/operators/<id>/` | карточка |

### Оператор: заявки и участники
| Старое | API | Экран |
|---|---|---|
| `/application/` (мероприятия ≤600 дней, свои заявки) | ✔ `GET /events/`, `GET /requests/` | `/cabinet` |
| `/create/<event>/` | ＋ `POST /api/v1/requests/` | кнопка |
| `/show/<req>/` | ✔ `GET /requests/<id>/` + ＋ участники заявки | `/requests/[id]` |
| `/add_attendee/<req>/` | ✔ `POST /api/v1/attendees/` (multipart, `services/intake`) — проверить паритет с HTML-формой | форма |
| `/update_attendee/<id>/` | ✔ `PUT`/`PATCH /attendees/<id>/` | форма |
| `/delete_attendee/` (последний удаляет заявку) | ✔ `DELETE /attendees/<id>/` — проверить удаление пустой заявки | строка |
| `/preview/<req>/`, `/back_to_change/<req>/` | ＋ `POST /requests/<id>/preview/`, `/edit/` | `/requests/[id]` |
| `/send/<req>/` (всё или ничего) | ＋ `POST /requests/<id>/send/` | кнопка |
| `/delete_request/<req>/` | ＋ `DELETE /requests/<id>/` | кнопка |
| возвраты на доработку (входящие) | ✔ данные в attendee + ＋ фильтр `status=draft&returned=1` | `/cabinet` |

### Суперопператор: проверка и выгрузка
| Старое | API | Экран |
|---|---|---|
| `/dashboard/<event>/` | ＋ `GET /api/v1/events/<id>/dashboard/` (то же, что `views/dashboard.py`) | `/events/[id]/dashboard` |
| `/review/<event>/` + start/approve/return | ✔ `attendees` actions + ＋ `GET /events/<id>/review-queue/` | `/events/[id]/review` |
| `/export_delta/<event>/<req>/` | ＋ `POST /api/v1/events/<id>/requests/<req>/export/` | дашборд |
| `/export_package/<uuid>/download/` | ＋ `GET /api/v1/export-packages/<uuid>/download/` (стрим, 409 при изменениях) | дашборд |
| `/export_package/<uuid>/acknowledge/` | ＋ `POST /api/v1/export-packages/<uuid>/acknowledge/` | дашборд |
| `download_json`, `download_guests_json`, `download_all_guests_json`, `download_request_json` | ＋ `GET /api/v1/events/<id>/reconciliation.json` и т.д. | карточка мероприятия |
| `/download_photos/<event>/`, `/download_file/`, `/check_archive_status/` | ＋ `GET /api/v1/events/<id>/photos.zip` (стрим) | карточка |

### Прочее
| Старое | Что делаем |
|---|---|
| Django-админка `/embankment/` | Остаётся как есть: прямое редактирование записей и справочников |
| Справочники | ✔ `GET /api/v1/directories/`; в формах — выпадающие списки с кодами СГО |
| Импорт KazEnergy / Avalon (cron) | Остаётся в Django; в UI — ＋ экран настроек партнёров и журнал приёма (`PartnerReceipt`) |
| QR (`/qr/`) | В текущем коде отключён (503) из-за открытого ИИН. Оставляем выключенным; бейджи второго этапа его заменяют |
| `/auth_check/`, `/health*` | Без изменений |

## Состояние на 28.11.2026

Этапы 1–5 сделаны (ветка `feature/nextjs-ui`). Как реализовано:

* Вход, профиль, смена пароля — `views/auth_api.py` (`/api/v1/auth/…`).
* Кабинет и заявки оператора — `views/request_api.py` (`/api/v1/cabinet/`, `/api/v1/requests/…`);
  участники — существующий `AttendeeViewSet` + запрет добавлять в отправленную заявку,
  удаление пустой заявки, лимит 20 записей в час.
* Администратор — `views/admin_api.py` (`/api/v1/admin/…`).
* Проверка и выгрузка — `views/staff_api.py` (`/api/v1/staff/…`).
* Выгрузки файлов, установка пароля по ссылке, Django-админка — прежние адреса Django.
* Тесты: `tests/test_auth_api.py`, `test_web_operator_api.py`, `test_web_admin_api.py`,
  `test_web_staff_api.py`, `test_web_texts.py`.

Отличия от HTML, сделанные сознательно:

* При добавлении участника API по-прежнему принимает черновик без файлов (на этом
  построены React-SPA и тесты), а обязательность фото и скана, как в HTML, проверяет форма
  Next.js. Отправить заявку без файлов нельзя в обоих случаях.
* Новый пароль при смене проверяется стандартными валидаторами Django (HTML-страница
  их не вызывала; ссылка-активация вызывает).
* Удаление заявки, участника, мероприятия и оператора спрашивает подтверждение.

## Этапы

1. **Каркас.** `web/` — Next.js; dev-прокси на Django; вход, `me`, выход, смена пароля, активация оператора; шапка, роли, RU/KZ/EN.
2. **Админ.** Мероприятия (список, создание, карточка, удаление, категории, иерархия), операторы (создание, карточка, привязки, повторная ссылка, деактивация, удаление).
3. **Оператор.** Кабинет, заявки (создание, просмотр, предпросмотр, отправка, удаление), участники (форма с файлами и справочниками, редактирование, удаление, возвраты).
4. **Суперопператор.** Дашборд, очередь проверки, пакеты выгрузки, JSON-сверки, ZIP фото.
5. **Сборка.** Dockerfile для `web/`, nginx и compose, e2e-сценарии по всем экранам, сверка со старыми HTML-страницами.
6. **Новое (второй этап).** Исполнение результата СГО, бейджи, саморегистрация, API-токены, доп. поля, просмотр аудита.

Каждый новый эндпоинт получает тесты в `eventproject/tests/` по образцу существующих: права по матрице `rbac_matrix.py`, аудит, CSRF.
