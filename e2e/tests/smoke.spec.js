// @ts-check
const { test, expect } = require('@playwright/test');

const ADMIN = { username: 'e2e_admin', password: 'E2eAdminPass123!' };
const OPERATOR = { username: 'e2e_operator', password: 'E2eOperatorPass123!' };
const VALID_IIN = '900215300007';

async function login(page, { username, password }) {
  await page.goto('/user_login/');
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await Promise.all([page.waitForNavigation(), page.click('form[action="/user_login/"] button[type="submit"], form[action="/user_login/"] input[type="submit"]')]);
}

test.describe('Health и доступность', () => {
  test('GET /api/health/ — БД доступна', async ({ request }) => {
    const res = await request.get('/api/health/');
    expect(res.status()).toBe(200);
    expect(await res.json()).toEqual({ status: 'ok', db: 'ok' });
  });

  test('страницы логина рендерятся на 3 языках', async ({ page }) => {
    for (const path of ['/user_login/', '/kz/', '/en/']) {
      await page.goto(path);
      await expect(page.locator('input[name="username"]')).toBeVisible();
      await expect(page.locator('input[name="password"]')).toBeVisible();
    }
  });
});

test.describe('Аутентификация', () => {
  test('неверный пароль не пускает', async ({ page }) => {
    await page.goto('/user_login/');
    await page.fill('input[name="username"]', ADMIN.username);
    await page.fill('input[name="password"]', 'wrong-password');
    await page.click('form[action="/user_login/"] button[type="submit"], form[action="/user_login/"] input[type="submit"]');
    // остаёмся неавторизованными: кабинет недоступен
    await page.goto('/avmac/');
    await expect(page).toHaveURL(/user_login/);
  });

  test('суперпользователь попадает в /avmac/', async ({ page }) => {
    await login(page, ADMIN);
    await expect(page).toHaveURL(/\/avmac\//);
    await expect(page.locator('form[action="/create_event/"]')).toBeVisible();
  });

  test('оператор попадает в /application/ и видит своё мероприятие', async ({ page }) => {
    await login(page, OPERATOR);
    await expect(page).toHaveURL(/\/application\//);
    await expect(page.locator('body')).toContainText('E2E Мероприятие');
  });
});

test.describe('Администратор: мероприятия', () => {
  test('создание мероприятия через форму /avmac/', async ({ page }) => {
    await login(page, ADMIN);
    const form = page.locator('form[action="/create_event/"]');
    await form.locator('input[name="name_rus"]').fill('Playwright Саммит');
    await form.locator('input[name="name_kaz"]').fill('Playwright Саммиті');
    await form.locator('input[name="name_eng"]').fill('Playwright Summit');
    await form.locator('input[name="event_code"]').fill('PW-001');
    await form.locator('input[name="date_start"]').fill('2026-07-01');
    await form.locator('input[name="date_end"]').fill('2026-07-03');
    await form.locator('select[name="city"]').selectOption({ index: 0 });
    await Promise.all([page.waitForNavigation(), form.locator('button[type="submit"], input[type="submit"]').first().click()]);
    await expect(page.locator('body')).toContainText('Playwright Саммит');
  });

  test('DRF: /api/v1/rbac-check/ возвращает роль superuser', async ({ page }) => {
    await login(page, ADMIN);
    const res = await page.request.get('/api/v1/rbac-check/');
    expect(res.status()).toBe(200);
    expect(await res.json()).toEqual({ role: 'superuser' });
  });
});

test.describe('Оператор: заявка', () => {
  test('создание заявки и форма добавления участника', async ({ page }) => {
    await login(page, OPERATOR);
    await Promise.all([page.waitForNavigation(), page.click('a[href^="/create/"]')]);
    // создание заявки ведёт на request.html; на странице есть переход к форме участника
    await expect(page).toHaveURL(/\/(create|show)\//);
    await expect(page.locator('body')).toContainText(/участник|заявк/i);
  });

  test('DRF: rbac-check для оператора', async ({ page }) => {
    await login(page, OPERATOR);
    const res = await page.request.get('/api/v1/rbac-check/');
    expect(await res.json()).toEqual({ role: 'operator' });
  });

  test('DRF: оператору запрещён список событий (IsSuperoperator)', async ({ page }) => {
    await login(page, OPERATOR);
    const res = await page.request.get('/api/v1/events/');
    expect(res.status()).toBe(403);
  });
});

test.describe('QR-модуль', () => {
  // /qr/ требует логина (security hardening) — авторизуемся оператором.
  test('валидный ИИН → страница успеха с QR-кодом', async ({ page }) => {
    await login(page, OPERATOR);
    await page.goto('/qr/');
    await page.fill('input[name="iin"]', VALID_IIN);
    await Promise.all([page.waitForNavigation(), page.click('#submitBtn, button[type="submit"]')]);
    await expect(page).toHaveURL(/\/qr\/success\/\d+/);
    await expect(page.locator('img.qr-code-image')).toBeVisible();
  });

  test('невалидный ИИН (не 12 цифр) не проходит', async ({ page }) => {
    await login(page, OPERATOR);
    await page.goto('/qr/');
    await page.fill('input[name="iin"]', '123');
    await page.click('#submitBtn, button[type="submit"]');
    await expect(page).toHaveURL(/\/qr\/?$/); // остаёмся на форме
  });
});

test.describe('Безопасность (регрессия фиксов)', () => {
  test('path traversal в media недоступен', async ({ page }) => {
    await login(page, ADMIN);
    // маршрут protected_media закомментирован — /media/../settings.py не должен отдавать файлы
    const res = await page.request.get('/media/..%2f..%2feventproject%2fsettings.py');
    // 400 — Django сам отклоняет подозрительный путь (SuspiciousOperation)
    expect([400, 404, 403, 301, 302]).toContain(res.status());
    // проверяем, что не отдан исходник settings.py (debug-страница 400 содержит ЛЕЙБЛ "SECRET_KEY" с маской — это норма)
    const body = await res.text();
    expect(body).not.toContain('from decouple import config');
  });

  test('неавторизованный доступ к кабинетам редиректит на логин', async ({ page }) => {
    for (const path of ['/avmac/', '/application/', '/show_event/1/']) {
      const res = await page.request.get(path, { maxRedirects: 0 });
      expect([302, 301]).toContain(res.status());
      expect(res.headers()['location']).toContain('user_login');
    }
  });
});
