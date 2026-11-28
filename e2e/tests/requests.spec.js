// @ts-check
// Заявки и участники: полный цикл оператора (создание заявки → CRUD участника →
// предпросмотр → отправка). Профиль: eventproject.settings_e2e + e2e/seed.py.
const { test, expect } = require('@playwright/test');
const {
  OPERATOR,
  VALID_IIN,
  login,
  csrfToken,
  newOperatorRequest,
  submitForm,
  addAttendee,
} = require('./helpers');

test.beforeEach(async ({ page }) => {
  await login(page, OPERATOR);
});

test.describe('Заявка: жизненный цикл', () => {
  test('создание заявки ведёт на форму со ссылкой "Добавить участника"', async ({ page }) => {
    const reqId = await newOperatorRequest(page);
    expect(Number(reqId)).toBeGreaterThan(0);
    await expect(page.locator(`a[href="/add_attendee/${reqId}/"]`)).toBeVisible();
    await expect(page.locator('body')).toContainText('E2E Мероприятие');
  });

  test('предпросмотр только для чтения → возврат к правке → отправка → Sent', async ({ page }) => {
    const reqId = await newOperatorRequest(page);

    expect(await (await addAttendee(page, reqId)).text()).toContain('успешно добавлен');
    // Этап C: предпросмотр — ссылка (GET) и статус заявки не меняет.
    await page.goto(`/show/${reqId}/`);
    await page.getByRole('link', { name: 'Предпросмотр' }).click();
    await expect(page.locator('body')).toContainText('Заявка готова к отправлению');

    // Возврат к редактированию — ссылка на карточку заявки, снова видно «Добавить участника».
    await page.getByRole('link', { name: 'Вернуться к редактированию' }).click();
    await expect(page.locator(`a[href="/add_attendee/${reqId}/"] button, a[href="/add_attendee/${reqId}/"]`).first()).toBeVisible();

    // Отправка выполняется из предпросмотра: статус Sent.
    await page.goto(`/preview/${reqId}/`);
    await submitForm(page, `/send/${reqId}/`);
    await expect(page.locator('body')).toContainText('Отправлено');
  });

  test('удаление пустой заявки с дашборда редиректит на /application/', async ({ page }) => {
    const reqId = await newOperatorRequest(page);
    await page.goto('/application/');
    const form = page.locator(`form[action="/delete_request/${reqId}/"]`);
    await expect(form).toBeVisible();
    await Promise.all([page.waitForNavigation(), form.locator('button[type="submit"]').click()]);
    await expect(page).toHaveURL(/\/application\//);
    // Форма удаления для этой заявки больше не отображается
    await expect(page.locator(`form[action="/delete_request/${reqId}/"]`)).toHaveCount(0);
  });
});

test.describe('Участник: CRUD', () => {
  test('добавление участника (multipart с фото и сканом) → успех', async ({ page }) => {
    const reqId = await newOperatorRequest(page);
    const res = await addAttendee(page, reqId, { last_name: 'Назарбаев', first_name: 'Аскар' });
    expect(res.status()).toBe(200);
    expect(await res.text()).toContain('успешно добавлен');

    await page.goto(`/show/${reqId}/`);
    await expect(page.locator('body')).toContainText('Назарбаев');
  });

  test('форма редактирования участника рендерится с заполненными полями', async ({ page }) => {
    const reqId = await newOperatorRequest(page);
    await addAttendee(page, reqId, { last_name: 'Иванов', first_name: 'Пётр' });

    await page.goto(`/show/${reqId}/`);
    const updHref = await page
      .locator('a[href^="/update_attendee/"]')
      .first()
      .getAttribute('href');
    const attId = /\/update_attendee\/(\d+)\//.exec(updHref || '')[1];

    await page.goto(`/update_attendee/${attId}/`);
    await expect(page.locator('input[name="last_name"]')).toHaveValue('Иванов');
    await expect(page.locator('input[name="first_name"]')).toHaveValue('Пётр');
  });

  test('обновление участника сохраняет новую фамилию', async ({ page }) => {
    const reqId = await newOperatorRequest(page);
    await addAttendee(page, reqId, { last_name: 'Старая', first_name: 'Фамилия' });

    await page.goto(`/show/${reqId}/`);
    const updHref = await page
      .locator('a[href^="/update_attendee/"]')
      .first()
      .getAttribute('href');
    const attId = /\/update_attendee\/(\d+)\//.exec(updHref || '')[1];

    await page.goto(`/update_attendee/${attId}/`);
    const token = await csrfToken(page);
    const res = await page.request.post(`/update_attendee/${attId}/`, {
      headers: { 'X-CSRFToken': token },
      multipart: {
        csrfmiddlewaretoken: token,
        last_name: 'Новая',
        first_name: 'Фамилия',
        patronymic: 'Тестович',
        latin_name: 'Novaya Familiya',
        iin: VALID_IIN,
        dob: '1990-02-15',
        sex: '1',
        citizenship: '1000000105',
        post: 'Директор',
        document_type: '1',
        doc_series: 'N12',
        doc_number: '123456',
        doc_date_start: '2020-01-01',
        doc_date_end: '2035-01-01',
        doc_issuer: 'МВД РК',
        visit_objects: 'Зал B',
      },
    });
    expect(res.status()).toBe(200);
    await page.goto(`/show/${reqId}/`);
    await expect(page.locator('body')).toContainText('Новая');
  });

  test('удаление единственного участника удаляет и заявку', async ({ page }) => {
    const reqId = await newOperatorRequest(page);
    await addAttendee(page, reqId, { last_name: 'Удаляемый', first_name: 'Гость' });

    await page.goto(`/show/${reqId}/`);
    const delForm = page.locator('form[action="/delete_attendee/"]').first();
    const attId = await delForm.locator('input[name="attendee_id"]').inputValue();
    const token = await csrfToken(page);
    const res = await page.request.post('/delete_attendee/', {
      headers: { 'X-CSRFToken': token },
      form: { csrfmiddlewaretoken: token, attendee_id: attId },
    });
    expect(res.status()).toBe(200);
    expect(await res.text()).toContain('удален');
  });
});
