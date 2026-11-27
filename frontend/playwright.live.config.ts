// Этап E: сквозной сценарий против живых серверов (Django 18811 на PostgreSQL, Vite 18812).
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e-live',
  reporter: 'list',
  workers: 1,
  projects: [{ name: 'chrome', use: { channel: 'chrome', locale: 'ru-RU' } }],
})
