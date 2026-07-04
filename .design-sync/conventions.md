# Конвенции «EventProject DS» (система аккредитации, токен-слой «Тихий сланец»)

## Обёртка и базовые стили
- Корень приложения оборачивай в `<div id="react-root">` — на этом id висят базовые стили: фон страницы `var(--canvas)` (#f4f5f6, никогда чистый #fff), цвет текста, system-ui-шрифт 16px и **min-height 44px для всех кнопок/инпутов/селектов** (anti-fatigue touch target). Без этой обёртки страница теряет канву и базовую типографику.
- Компонентам с данными/роутингом (`AppShell`, `AttendeeForm`) нужен контекст React Query + Router: оберни приложение в экспортируемый `DSPreviewProvider` (даёт QueryClient c retry:false, MemoryRouter, ThemeProvider и инициализацию i18n). Без него `AppShell` падает на `useQuery`.
- Строки интерфейса компонентов приходят из встроенного i18n (русский по умолчанию; kz/en частично). Свои тексты пиши по-русски — это операторский кабинет для Казахстана.
- Тёмная тема = класс `.dark` на `<html>` (вешает `ThemeProvider`/`useTheme`); палитра под `.dark` уже в CSS, но продукт пока шипит light как дефолт.

## Идиома стилей: Tailwind-утилиты на токенах
CSS скомпилирован JIT из приложения — **существуют только классы из списка ниже; произвольные Tailwind-классы (например `px-4`, `bg-canvas`) отсутствуют**. Для нестандартной раскладки используй inline-style или `var(--…)`.

- Поверхности/границы: `bg-surface` `bg-surface-muted` `bg-overlay` · `border` `border-border` (декоративная) `border-border-strong` `border-input-border` (интерактивные контролы, ≥3:1) · `rounded` `rounded-md` (6px) `rounded-lg` `rounded-full` · `shadow-lg`
- Текст: `text-text` `text-text-muted` · размеры `text-xs/sm/base/lg/xl/2xl` · `font-medium/semibold/bold` · `tabular-nums` `truncate` `uppercase`
- Акцент (глубокий синий): `bg-primary` `text-primary-foreground` `hover:bg-primary-hover` `bg-primary-tint` `text-primary` `border-primary`
- Статусы (всегда точка/иконка + текст, цвет не единственный носитель): `bg-status-{active|checking|sent|exported|rejected}-tint` + `text-status-{…}` + `bg-status-{…}` (для dot)
- Фокус/состояния: `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary` (+`ring-offset-2`) · `hover:bg-surface-muted` · `disabled:opacity-50 disabled:pointer-events-none` · `transition-colors`
- Раскладка: `flex flex-col flex-wrap flex-1 shrink-0 items-center items-start justify-between/center/end` · `grid grid-cols-1 sm:grid-cols-2 md:grid-cols-[280px_1fr]` · `gap-1/1.5/2/3/4/6` `space-y-1/1.5/2/3/4` · `w-full w-56 max-w-xs/md/2xl/4xl/5xl` `min-h-svh` `h-11 h-12`
- Отступы (только эти шаги): `p-0/2/3/4/6` · `px-1.5/2/3/5/6` · `py-0.5/1/2/3/4/8/12` · `mt-1/3/4/5/8` `mb-1/2/4/6`

## Где правда
- Токены (`:root` и `.dark`): в конце `styles.css`-цепочки (`_ds_bundle.css`) — `--canvas --surface --surface-muted --border --border-strong --input-border --overlay --text --text-muted --primary(-hover|-tint|-foreground) --status-*(-tint) --radius`. Читай их перед стилизацией.
- API каждого компонента — `components/<group>/<Name>/<Name>.d.ts`, примеры композиции — `<Name>.prompt.md`.

## Компоненты (10)
`Button` (variant: default|outline|ghost; size: default|lg) · `StatusBadge` (status: draft|submitted|in_review|ready|exported) · `LanguageSwitcher` · `ReturnReasonDialog` (open, pending, onClose, onSubmit) · `UploadZone`/`PhotoUpload`/`DocumentUpload` (file, onFileChange, error, existingUrl) · `AppShell` (каркас: шапка+левый nav; без бэкенда nav минимальный) · `AttendeeForm` (поля `surname`/`firstname`; readOnly/initialValues для edit) · `ThemeProvider`+`useTheme`

## Идиоматичный пример
```tsx
<DSPreviewProvider>
  <div id="react-root">
    <div className="p-6" style={{ maxWidth: 720 }}>
      <div className="rounded-lg border border-border bg-surface p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-text">Заявка участника</h2>
          <StatusBadge status="in_review" />
        </div>
        <p className="text-sm text-text-muted mb-4">Проверьте данные перед отправкой.</p>
        <div className="flex justify-end gap-3">
          <Button variant="outline">Отмена</Button>
          <Button>Отправить на проверку</Button>
        </div>
      </div>
    </div>
  </div>
</DSPreviewProvider>
```
