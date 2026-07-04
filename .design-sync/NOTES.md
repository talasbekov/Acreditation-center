# design-sync NOTES — eventproject frontend

- Репо — Django-бэкенд + Vite React **приложение** (`frontend/`), не библиотека: нет library-build/`.d.ts`. Конвертер работает в synth-entry режиме из `src/`, список компонентов пинится через `componentSrcMap` (9 UI-компонентов + ThemeProvider; `RequireAuth: null` — router-guard, не UI).
- **CSS**: Tailwind v4 компилируется только vite-билдом приложения (`npm run build`); `buildCmd` копирует `dist/assets/index-*.css` в стабильный путь `frontend/.ds-css/app.css` (gitignored) → `cssEntry`. Токены «Тихий сланец» (`:root` vars + `@theme inline`) въезжают внутри этого файла.
- ⚠️ **Tailwind JIT сканирует только исходники приложения** — utility-классы, которых нет в app-коде, в скомпилированном CSS отсутствуют. Авторские превью (`.design-sync/previews/*.tsx`) должны использовать только классы, встречающиеся в приложении, либо inline-styles для glue-разметки.
- **i18n**: `src/i18n/index.ts` — side-effect init (i18next default instance); превью-провайдер (`.design-sync/preview-support/provider.tsx`, подключён через `extraEntries` + `cfg.provider = DSPreviewProvider`) импортирует его + QueryClient + MemoryRouter + ThemeProvider. kz-каталоги частично пустые → фолбэк на ru (так задумано).
- **Playwright**: репо пинит `@playwright/test` 1.61.1 → chromium build **1228**, уже в кэше `~/.cache/ms-playwright/` — для render-check ставить playwright@1.61.1, браузер качать не надо.
- Компоненты с сетевыми запросами (AppShell/useRole → `GET /api/v1/rbac-check/`, AttendeeForm add-mode → `getRequests`) в превью деградируют мягко: retry:false в провайдере, fetch падает → минимальный nav / пустой select. Не чинить — так и задумано.
- Шрифты: system-ui стек, `@font-face` нет — нечего шипить.

## Уроки авторинга превью (wave 1, 2026-07-04)

- **Overlay/fixed компоненты** (ReturnReasonDialog): `.ds-single` в карточке имеет `transform:translateZ(0)` → `fixed inset-0` позиционируется от него, а у корня истории нет высоты → диалог вылезает вверх. Фикс в превью: обёртка `style={{transform:'translateZ(0)', height:592, position:'relative', overflow:'hidden'}}` (592 ≈ viewport 640 − паддинги) — диалог центрируется в ней.
- Изменение `cfg.overrides` (viewport/cardMode) требует полного `package-build.mjs` — `preview-rebuild.mjs` отбивает `[CONFIG_STALE]`.
- **Файловые компоненты**: File-объекты в превью не конструировать (битая картинка через objectURL); заполненное состояние — `existingUrl` + inline SVG data-URI (серый портрет 3×4). Нативный file-input («Choose File») — задуманный вид компонента, не unstyled-дефект.
- **Data-driven компоненты** (AppShell): стаб `window.fetch` на верхнем уровне модуля превью (до маунта): `rbac-check` → `{role:'superuser'}` (полный nav), `/attendees` → `{count:3,…}` (бейдж возвратов). Паттерн — в `.design-sync/previews/AppShell.tsx`.
- **AttendeeForm**: поля называются `surname`/`firstname` (не lastName!); KZ countryId = `'1000000105'`; для ReadOnly-истории нужен ЧЕКСУМ-валидный ИИН, согласованный с birthDate (900322400818 ↔ 1990-03-22), иначе красная рамка «неверная контрольная цифра». Категория в edit — fallback-опция «Категория #N».
- Длинные формы в `cardMode: column` уходят за высоту карточки — это граница вьюпорта, не обрезание; грейдить по видимому хрому.

## Re-sync (процедура)

1. Скопировать свежие скрипты skill'а в `.ds-sync/` (см. §7 sub-skill) + `npm i esbuild ts-morph @types/react typescript playwright@<версия из frontend/package-lock, сейчас 1.61.1>` там.
2. `cd frontend && npm run build && mkdir -p .ds-css && cp dist/assets/index-*.css .ds-css/app.css && npx tsc -p tsconfig.dstypes.json` (= cfg.buildCmd).
3. Скачать анкер: `DesignSync(get_file, "_ds_sync.json")` → `.design-sync/.cache/remote-sync.json`.
4. `node .ds-sync/resync.mjs --config .design-sync/config.json --node-modules frontend/node_modules --out ./ds-bundle --remote .design-sync/.cache/remote-sync.json`.

## Re-sync risks (что может тихо протухнуть)

- **Tailwind JIT-словарь**: `conventions.md` перечисляет классы, существующие в скомпилированном CSS приложения. Если приложение перестанет использовать класс — он исчезнет из CSS, а conventions будет врать. Валидационный проход conventions-шага на re-sync обязателен (grep классов по `ds-bundle/_ds_bundle.css`).
- **fetch-стабы в превью** (`AppShell.tsx`: `rbac-check` → `{role}`, `/attendees` → `{count,…}`; `AttendeeForm.tsx`: `/requests`) прибиты к текущим DRF-контрактам. Изменение контракта не уронит превью (деградация до минимального nav/пустого select), но карточка станет беднее — проверять сheets.
- **AttendeeForm**: превью ReadOnly использует чексум-валидный ИИН 900322400818 ↔ birthDate 1990-03-22 и поля `surname`/`firstname`; смена схемы/алгоритма validateIIN сломает зелёную ✅ или покрасит рамку.
- **`.ds-types/`** генерится `buildCmd` из `ds.entry.ts`; `frontend/package.json:"types"` указывает туда. Новые компоненты добавлять и в `ds.entry.ts`, и в `componentSrcMap`.
- **provider-модуль** (`.design-sync/preview-support/provider.tsx`) импортирует `frontend/src/i18n` относительным путём — переезд i18n-модуля сломает все превью разом (провайдер-ошибка во всех карточках).
- **cp dist/assets/index-*.css** предполагает ровно один css в dist — если vite начнёт code-splitting CSS, glob скопирует не то.
- **chromium 1228** в кэше ↔ playwright 1.61.1: при апгрейде `@playwright/test` в репо переустановить playwright в `.ds-sync` под новый пин.
- Частично верифицировано: тёмная тема (`.dark`-палитра со статусом [ASSUMPTION] в index.css) в превью не прогонялась — карточки рендерятся только в light.
