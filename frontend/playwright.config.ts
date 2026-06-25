import { defineConfig, devices } from '@playwright/test'

/**
 * P2-10 / browser-e2e — закрывает ручной-QA пробел из Story 5.1–5.5.
 *
 * Запускает Vite dev-сервер и гоняет реальные браузерные сценарии React-приложения
 * (редирект без сессии, загрузка списка, предзаполнение edit-формы, residency-toggle).
 * Бэкенд DRF замокан через `page.route('**\/api/v1/**')` — тестируем поведение БРАУЗЕРА
 * (роутинг/формы/ошибки), не бэкенд-логику (она покрыта Django-тестами). Для полного
 * сквозного прогона против живого Django/Postgres — поднять стек и убрать моки.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    // Контейнер/CI: chromium без user-namespace sandbox.
    launchOptions: { args: ['--no-sandbox', '--disable-dev-shm-usage'] },
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'npm run dev -- --port 5173 --strictPort',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
