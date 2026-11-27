// @ts-check
// Мультиязычность (kz/en операторские кабинеты) + крайние случаи QR-модуля.
// Профиль: eventproject.settings_e2e + e2e/seed.py.
const { test, expect } = require('@playwright/test');
const { OPERATOR, login } = require('./helpers');

test.describe('Мультиязычность: кабинет оператора', () => {
  test('логин через казахскую форму /kz/ ведёт в /kz/application/', async ({ page }) => {
    await page.goto('/kz/');
    await page.fill('input[name="username"]', OPERATOR.username);
    await page.fill('input[name="password"]', OPERATOR.password);
    await Promise.all([
      page.waitForNavigation(),
      page.click('form[action="/kz/user_login/"] button[type="submit"]'),
    ]);
    await expect(page).toHaveURL(/\/kz\/application\//);
    await expect(page.locator('body')).toContainText('E2E Іс-шара'); // name_kaz
    await expect(page.locator('form[action^="/kz/create/"] button')).toBeVisible();
  });

  test('казахский кабинет: казахский UI и событие', async ({ page }) => {
    await login(page, OPERATOR);
    await page.goto('/kz/application/');
    await expect(page.locator('body')).toContainText('Шара'); // казахский заголовок
    await expect(page.locator('a[href="/kz/logout/"]')).toContainText('Шығу');
    await expect(page.locator('body')).toContainText('E2E Іс-шара');
  });

  test('английский кабинет: английский UI и событие', async ({ page }) => {
    await login(page, OPERATOR);
    await page.goto('/en/application/');
    await expect(page.locator('body')).toContainText('Welcome');
    await expect(page.locator('a[href="/en/logout/"]')).toContainText('Sign out');
    await expect(page.locator('body')).toContainText('E2E Event'); // name_eng
    await expect(page.locator('form[action^="/en/create/"] button')).toBeVisible();
  });
});

test.describe('QR-модуль: доступ и валидация', () => {
  test('неавторизованный доступ к /qr/ редиректит на логин', async ({ page }) => {
    const res = await page.request.get('/qr/', { maxRedirects: 0 });
    expect([301, 302]).toContain(res.status());
    expect(res.headers()['location']).toContain('user_login');
  });

  test('выдача приостановлена, форма персональных данных отсутствует', async ({ page }) => {
    await login(page, OPERATOR);
    const res = await page.goto('/qr/');
    expect(res.status()).toBe(503);
    await expect(page.getByRole('heading', { name: /Выдача QR-кодов временно приостановлена/ })).toBeVisible();
    await expect(page.locator('input[name="iin"], img.qr-code-image')).toHaveCount(0);
  });

  test('страница исторического кода недоступна', async ({ page }) => {
    await login(page, OPERATOR);
    const res = await page.goto('/qr/success/1/');
    expect(res.status()).toBe(404);
    await expect(page.getByRole('heading', { name: 'QR-код недоступен' })).toBeVisible();
    await expect(page.locator('img.qr-code-image')).toHaveCount(0);
  });
});
