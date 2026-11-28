# web/ — интерфейс АЦ на Next.js

Новый интерфейс аккредитационного центра. Бэкенд — Django этого же репозитория:
вся логика (проверки ИИН и документов, дубли, статусы, шифрование, аудит) в нём,
интерфейс ходит в `/api/v1/` на том же адресе с сессией Django и CSRF.

План и карта «старая страница → API → экран»: [`../docs/nextjs-migration-plan.md`](../docs/nextjs-migration-plan.md).

## Экраны

| Роль | Экран | Старая страница |
|---|---|---|
| все | `/login`, `/change-password` | `/user_login/`, `/change_password/` |
| оператор | `/cabinet` | `/application/` |
| оператор | `/requests/[id]` (+ `?preview=1`) | `/show/<id>/`, `/preview/<id>/` |
| оператор | `/requests/[id]/add`, `/attendees/[id]/edit` | `/add_attendee/`, `/update_attendee/` |
| администратор | `/admin/events`, `/admin/events/[id]` | `/avmac/`, `/show_event/<id>/` |
| администратор | `/admin/operators`, `/admin/operators/[id]` | `/avmac/`, `/show_operator/<id>/` |
| супероператор, админ | `/staff`, `/staff/[id]/review`, `/staff/[id]/dashboard` | `/review/<id>/`, `/dashboard/<id>/` |
| супероператор, админ | `/staff/[id]/badges` | — (второй этап) |
| оператор, админ | `/events/[id]/settings` (доп. поля, ссылки, токены) | — (второй этап) |
| без входа | `/register/[token]` | — (второй этап) |
| администратор | `/admin/audit` | — (второй этап) |

Выгрузки (JSON-сверки, ZIP фото, пакеты) и установка пароля по ссылке из письма
остаются адресами Django — интерфейс ссылается на них.

## Тексты и языки

RU/KZ/EN. Ключ перевода — русская строка, как `{% t %}` в шаблонах. Переводы
берутся из словарей Django (`ui_text.py`, `page_lang.py`, тексты ошибок API,
подписи статусов) — после их правки обновите копии:

```
python manage.py export_web_texts
```

Строки, которых в старой АЦ не было, — в `lib/texts.ts`.

## Разработка

Нужны Python-окружение проекта и Node 22 с pnpm.

```
# Django на SQLite с демо-данными (учётки и пароль — в scripts/dev/seed_dev.py)
python manage.py migrate --settings=eventproject.settings_dev
python manage.py createcachetable --settings=eventproject.settings_dev
python scripts/dev/seed_dev.py
python manage.py runserver 127.0.0.1:8000 --settings=eventproject.settings_dev

# интерфейс: http://localhost:3000, запросы к Django проксируются (next.config.mjs)
cd web && pnpm install && pnpm dev
```

Проверка типов: `pnpm exec tsc --noEmit`.

## Сборка

`web/Dockerfile` (Next.js standalone) — сервис `ui` в `compose.release.yml`.
Наружу его публикует nginx из `frontend/release.nginx.conf`: экраны интерфейса
идут в `ui`, `/api/`, `/media/`, выгрузки и админка Django — в `app`; старые
точки входа (`/user_login/`, `/application/`, `/avmac/`) перенаправляются на новые.

Фоновые задачи (PDF бейджей) выполняет сервис `worker` (`manage.py run_jobs`), PDF
лежат в томе `private_files`. В разработке `settings_dev` выполняет задачи сразу
(`JOBS_RUN_INLINE`).
