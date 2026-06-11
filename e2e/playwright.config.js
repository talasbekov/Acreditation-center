// @ts-check
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  timeout: 30_000,
  retries: 0,
  workers: 1, // общая SQLite-база — без параллелизма
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:8088',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
});
