# scripts/ — наполнение справочников

Одноразовые скрипты для первичного заполнения таблиц `directories.*` из CSV.
Каждый скрипт сам поднимает Django (`DJANGO_SETTINGS_MODULE=eventproject.settings`)
и читает CSV, лежащий рядом (путь не зависит от текущей директории).

Запуск из корня проекта:

```bash
.venv/bin/python scripts/country_populate.py     # Country  <- countries.csv (разделитель ",")
.venv/bin/python scripts/populate_cities.py      # City     <- cities.csv     (разделитель ";")
.venv/bin/python scripts/populate_categories.py  # Category <- categories.csv (разделитель ";")
.venv/bin/python scripts/populate_docs.py         # DocumentType <- docs.csv  (разделитель ";")
```

> Используют боевой профиль `eventproject.settings` — нужен доступ к БД (Postgres)
> и переменные окружения из `.env`. Запускать на пустых/инициализируемых справочниках.
