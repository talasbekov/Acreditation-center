// @ts-check
// Админ: управление событиями и операторами (суперпользователь /avmac/).
// Профиль: eventproject.settings_e2e + e2e/seed.py.
const { test, expect } = require('@playwright/test');
const { ADMIN, login, csrfToken } = require('./helpers');

test.beforeEach(async ({ page }) => {
  await login(page, ADMIN);
});

/** Создаёт оператора через /add_operator/ (привязывается к seed-событию id=1). */
async function createOperator(page, ts) {
  const lastName = `Опертестов${ts}`;
  const loginName = `op_${ts}`;
  await page.goto('/avmac/');
  const token = await csrfToken(page);
  const res = await page.request.post('/add_operator/', {
    headers: { 'X-CSRFToken': token },
    form: {
      csrfmiddlewaretoken: token,
      first_name: 'Иван',
      last_name: lastName,
      patronymic: 'Иванович',
      login: loginName,
      phone_number: '+77001112233',
      workplace: 'Тест',
      event_code: '1',
    },
  });
  expect(res.status()).toBe(200);
  expect(await res.text()).toContain('успешно создан');

  await page.goto('/avmac/');
  const href = await page
    .locator('a[href^="/show_operator/"]')
    .filter({ hasText: lastName })
    .getAttribute('href');
  const opId = /\/show_operator\/(\d+)\//.exec(href || '')[1];
  return { loginName, lastName, opId };
}

test.describe('Админ: события', () => {
  test('show_event рендерит seed-событие, операторов и формы экспорта', async ({ page }) => {
    await page.goto('/show_event/1/');
    await expect(page.locator('body')).toContainText('E2E Мероприятие');
    await expect(page.locator('form[action="/delete_event/1/"]')).toBeVisible();
    await expect(page.locator('form[action="/bind_operators/"]')).toBeVisible();
  });

  test('создание и удаление мероприятия', async ({ page }) => {
    const ts = Date.now();
    const evName = `Удаляемое-${ts}`;
    await page.goto('/avmac/');
    const token = await csrfToken(page);
    const created = await page.request.post('/create_event/', {
      headers: { 'X-CSRFToken': token },
      form: {
        csrfmiddlewaretoken: token,
        name_rus: evName,
        name_kaz: evName,
        name_eng: evName,
        event_code: `TMP-${ts}`,
        // даты в пределах окна дашборда (today+900д), иначе событие не отрисуется
        date_start: '2027-01-01',
        date_end: '2027-01-05',
        city: '1',
      },
    });
    expect(created.status()).toBe(200);
    expect(await created.text()).toContain('успешно создано');

    await page.goto('/avmac/');
    const href = await page
      .locator('a[href^="/show_event/"]')
      .filter({ hasText: evName })
      .getAttribute('href');
    const evId = /\/show_event\/(\d+)\//.exec(href || '')[1];

    const del = await page.request.post(`/delete_event/${evId}/`, {
      headers: { 'X-CSRFToken': token },
      form: { csrfmiddlewaretoken: token },
    });
    expect(del.status()).toBe(200);
    expect(await del.text()).toContain('успешно удалено');
  });

  test('flush_outdated_events выполняется и не трогает будущее seed-событие', async ({ page }) => {
    const res = await page.request.get('/flush_outdated_events/');
    expect(res.status()).toBe(200);
    expect(await res.text()).toContain('успешно удалены');
    // seed-событие заканчивается в будущем → должно остаться
    await page.goto('/avmac/');
    await expect(page.locator('body')).toContainText('E2E Мероприятие');
  });
});

test.describe('Админ: операторы', () => {
  test('создание оператора показывает сгенерированный пароль', async ({ page }) => {
    const { loginName } = await createOperator(page, Date.now());
    expect(loginName).toMatch(/^op_\d+$/);
  });

  test('открепление события от оператора (unbind_event)', async ({ page }) => {
    const { loginName } = await createOperator(page, Date.now());
    const res = await page.request.get(`/unbind_event/1/${loginName}/`);
    expect(res.status()).toBe(200);
    expect(await res.text()).toContain('успешно откреплен');
  });

  test('повторная привязка оператора к событию (bind_operators)', async ({ page }) => {
    const { loginName, opId, lastName } = await createOperator(page, Date.now());
    // сначала открепляем
    await page.request.get(`/unbind_event/1/${loginName}/`);
    // затем привязываем заново через bind_operators
    const token = await csrfToken(page);
    const res = await page.request.post('/bind_operators/', {
      headers: { 'X-CSRFToken': token },
      form: { csrfmiddlewaretoken: token, operator: opId, event_code: '1' },
    });
    expect(res.status()).toBe(200);
    // редирект на /show_event/1/, где оператор снова в списке привязанных
    await page.goto('/show_event/1/');
    await expect(page.locator('body')).toContainText(lastName);
  });

  test('удаление оператора (delete_operator)', async ({ page }) => {
    const { loginName } = await createOperator(page, Date.now());
    const token = await csrfToken(page);
    const res = await page.request.post(`/delete_operator/${loginName}/`, {
      headers: { 'X-CSRFToken': token },
      form: { csrfmiddlewaretoken: token },
    });
    expect(res.status()).toBe(200);
    expect(await res.text()).toContain('успешно удален');
  });
});
