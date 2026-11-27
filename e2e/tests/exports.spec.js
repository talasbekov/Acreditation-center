// @ts-check
// Экспорт и выгрузки (только суперпользователь): JSON-экспорт, архивы, статус.
// Профиль: eventproject.settings_e2e + e2e/seed.py.
const { test, expect } = require('@playwright/test');
const { ADMIN, OPERATOR, login, csrfToken, newOperatorRequest, addAttendee, submitForm } = require('./helpers');

test.describe('Экспорт: контроль доступа и 404', () => {
  test('check_archive_status без архива → JSON not_found (админ)', async ({ page }) => {
    await login(page, ADMIN);
    const res = await page.request.get('/check_archive_status/1/');
    expect(res.status()).toBe(200);
    expect(await res.json()).toMatchObject({ status: 'not_found' });
  });

  test('оператору экспорт-эндпоинты недоступны (редирект на логин)', async ({ page }) => {
    await login(page, OPERATOR);
    const token = await csrfToken(page);
    // GET-эндпоинт
    const statusRes = await page.request.get('/check_archive_status/1/', { maxRedirects: 0 });
    expect([301, 302]).toContain(statusRes.status());
    expect(statusRes.headers()['location']).toContain('user_login');
    // POST-эндпоинт (user_passes_test срабатывает раньше require_POST)
    const jsonRes = await page.request.post('/download_json/1/', {
      headers: { 'X-CSRFToken': token },
      form: { csrfmiddlewaretoken: token },
      maxRedirects: 0,
    });
    expect([301, 302]).toContain(jsonRes.status());
    expect(jsonRes.headers()['location']).toContain('user_login');
  });

  test('download_file без архива → 404', async ({ page }) => {
    await login(page, ADMIN);
    const res = await page.request.get('/download_file/1/');
    expect(res.status()).toBe(404);
    expect(await res.text()).toContain('Архив не найден');
  });

  test('download_photos без директории медиа → 404', async ({ page }) => {
    await login(page, ADMIN);
    // несуществующее событие → каталога медиа гарантированно нет
    const res = await page.request.get('/download_photos/999999/');
    expect(res.status()).toBe(404);
  });

  test('download_json для несуществующего события → 404', async ({ page }) => {
    await login(page, ADMIN);
    const token = await csrfToken(page);
    const res = await page.request.post('/download_json/999999/', {
      headers: { 'X-CSRFToken': token },
      form: { csrfmiddlewaretoken: token },
    });
    expect(res.status()).toBe(404);
  });
});

test.describe('Внутренняя сверка идентификаторов', () => {
  test('повторная сверка показывает ту же отправленную заявку', async ({ page }) => {
    // 1) оператор создаёт и отправляет заявку
    await login(page, OPERATOR);
    const reqId = await newOperatorRequest(page);
    expect(await (await addAttendee(page, reqId)).text()).toContain('успешно добавлен');
    await page.goto(`/show/${reqId}/`);
    await submitForm(page, `/preview/${reqId}/`);
    await submitForm(page, `/send/${reqId}/`);

    // 2) администратор сверяет ID участников события
    await login(page, ADMIN);
    const token = await csrfToken(page);
    const res = await page.request.post('/download_json/1/', {
      headers: { 'X-CSRFToken': token },
      form: { csrfmiddlewaretoken: token },
    });
    expect(res.status()).toBe(200);
    expect(res.headers()['content-type']).toContain('application/json');
    const body = await res.json();
    expect(body).toHaveProperty('attendees');
    const row = body.attendees.find((attendee) => attendee.request === Number(reqId));
    expect(row).toEqual({ id: expect.any(Number), request: Number(reqId) });
    expect(res.headers()['cache-control']).toContain('no-store');
    await page.goto('/show_event/1/');
    await expect(page.getByText('Внутренняя сверка идентификаторов', { exact: true })).toBeVisible();
    await expect(page.locator('a[href="/show_request_to_admin/' + reqId + '"]')).toHaveClass(/btn-warning/);
    const repeated = await page.request.post('/download_json/1/', {
      headers: { 'X-CSRFToken': token },
      form: { csrfmiddlewaretoken: token },
    });
    expect((await repeated.json()).attendees).toContainEqual(row);
  });

  test('сверка идентификаторов одной заявки', async ({ page }) => {
    await login(page, OPERATOR);
    const reqId = await newOperatorRequest(page);

    await login(page, ADMIN);
    const token = await csrfToken(page);
    const res = await page.request.post(`/download_request_json/${reqId}/`, {
      headers: { 'X-CSRFToken': token },
      form: { csrfmiddlewaretoken: token },
    });
    expect(res.status()).toBe(200);
    expect(res.headers()['content-type']).toContain('application/json');
    const body = await res.json();
    expect(body).toHaveProperty('attendees');
  });
});
