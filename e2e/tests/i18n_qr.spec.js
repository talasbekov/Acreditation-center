// @ts-check
// Мультиязычность (kz/en операторские кабинеты) + крайние случаи QR-модуля.
// Профиль: eventproject.settings_e2e + e2e/seed.py.
const { test, expect } = require('@playwright/test');
const { OPERATOR, VALID_IIN, INVALID_IIN, login } = require('./helpers');

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
    await expect(page.locator('a[href^="/kz/create/"]')).toBeVisible();
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
    await expect(page.locator('a[href^="/en/create/"]')).toBeVisible();
  });
});

test.describe('QR-модуль: доступ и валидация', () => {
  test('неавторизованный доступ к /qr/ редиректит на логин', async ({ page }) => {
    const res = await page.request.get('/qr/', { maxRedirects: 0 });
    expect([301, 302]).toContain(res.status());
    expect(res.headers()['location']).toContain('user_login');
  });

  test('авторизованный: валидный ИИН → страница успеха с QR-кодом', async ({ page }) => {
    await login(page, OPERATOR);
    await page.goto('/qr/');
    await page.fill('input[name="iin"]', VALID_IIN);
    await Promise.all([
      page.waitForNavigation(),
      page.click('#submitBtn, button[type="submit"]'),
    ]);
    await expect(page).toHaveURL(/\/qr\/success\/\d+/);
    await expect(page.locator('img.qr-code-image')).toBeVisible();
    await expect(page.locator('body')).toContainText('ИИН');
  });

  test('невалидная контрольная цифра (12 цифр) не проходит', async ({ page }) => {
    await login(page, OPERATOR);
    await page.goto('/qr/');
    await page.fill('input[name="iin"]', INVALID_IIN);
    await page.click('#submitBtn, button[type="submit"]');
    // остаёмся на форме /qr/ с ошибкой валидации
    await expect(page).toHaveURL(/\/qr\/?$/);
    await expect(page.locator('body')).toContainText(/контрольн|Исправьте ошибки/i);
  });

  test('короткий ИИН (не 12 цифр) не проходит', async ({ page }) => {
    await login(page, OPERATOR);
    await page.goto('/qr/');
    await page.fill('input[name="iin"]', '123');
    await page.click('#submitBtn, button[type="submit"]');
    await expect(page).toHaveURL(/\/qr\/?$/);
  });
});
