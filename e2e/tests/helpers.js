// @ts-check
// Общие хелперы для E2E-набора (Playwright). Профиль: eventproject.settings_e2e.
const fs = require('fs');
const path = require('path');

const ADMIN = { username: 'e2e_admin', password: 'E2eAdminPass123!' };
const OPERATOR = { username: 'e2e_operator', password: 'E2eOperatorPass123!' };

// ИИН граждан РК для seed-события (countryId == "1000000105").
const VALID_IIN = '900215300007'; // проходит iin_kz_validator (корректная контрольная цифра)
const INVALID_IIN = '900215300008'; // 12 цифр, но неверная контрольная цифра

const FIXTURES = path.join(__dirname, '..', 'fixtures');
const PHOTO = path.join(FIXTURES, 'photo.png');
const DOC = path.join(FIXTURES, 'doc.png');

// Уникальный 12-значный ИИН для каждого участника. Дубликат ИИН в пределах
// события отклоняется (check_dublicate), а add_attendee не проверяет контрольную
// цифру — нужен лишь уникальный 12-значный номер.
let _iinCounter = 0;
function uniqueIin() {
  _iinCounter += 1;
  return (String(Date.now()) + String(_iinCounter).padStart(3, '0')).slice(-12);
}

/** Логин через основную форму /user_login/ (рус. кабинет). */
async function login(page, creds) {
  await page.goto('/user_login/');
  await page.fill('input[name="username"]', creds.username);
  await page.fill('input[name="password"]', creds.password);
  await Promise.all([
    page.waitForNavigation(),
    page.click(
      'form[action="/user_login/"] button[type="submit"], form[action="/user_login/"] input[type="submit"]'
    ),
  ]);
}

/**
 * Значение csrftoken-куки. Django принимает его как заголовок X-CSRFToken
 * и как поле csrfmiddlewaretoken (стандартный AJAX-паттерн).
 */
async function csrfToken(page) {
  const cookies = await page.context().cookies();
  const c = cookies.find((x) => x.name === 'csrftoken');
  return c ? c.value : '';
}

/**
 * Оператор создаёт новую заявку для seed-события и возвращает её id.
 * id извлекается из ссылки "Добавить участника" (/add_attendee/<id>/).
 */
async function newOperatorRequest(page) {
  await page.goto('/application/');
  await Promise.all([
    page.waitForNavigation(),
    page.locator('a[href^="/create/"]').first().click(),
  ]);
  const href = await page.locator('a[href^="/add_attendee/"]').first().getAttribute('href');
  const m = /\/add_attendee\/(\d+)\//.exec(href || '');
  if (!m) throw new Error('Не удалось получить id заявки из request.html');
  return m[1];
}

/**
 * POST multipart-формы участника в /add_attendee/<reqId>/.
 * Возвращает Playwright APIResponse. Тело успеха содержит "успешно добавлен".
 */
async function addAttendee(page, reqId, overrides = {}) {
  // GET формы добавляет csrftoken-куку и отдаёт скрытый csrfmiddlewaretoken.
  await page.goto(`/add_attendee/${reqId}/`);
  const token = await page.locator('input[name="csrfmiddlewaretoken"]').inputValue();
  const data = {
    csrfmiddlewaretoken: token,
    req_id: String(reqId),
    last_name: 'Тестов',
    first_name: 'Тест',
    patronymic: 'Тестович',
    latin_name: 'Testov Test',
    iin: uniqueIin(),
    dob: '1990-02-15',
    sex: '1',
    citizenship: '1000000105',
    category: '1',
    post: 'Инженер',
    document_type: '1',
    doc_series: 'N12',
    doc_number: '123456',
    doc_date_start: '2020-01-01',
    doc_date_end: '2035-01-01',
    doc_issuer: 'МВД РК',
    visit_objects: 'Зал A',
    ...overrides,
    // multipart требует buffer (filePath не поддерживается в request.post).
    photo: { name: 'photo.png', mimeType: 'image/png', buffer: fs.readFileSync(PHOTO) },
    doc_photo: { name: 'doc.png', mimeType: 'image/png', buffer: fs.readFileSync(DOC) },
  };
  return page.request.post(`/add_attendee/${reqId}/`, {
    headers: { 'X-CSRFToken': token },
    multipart: data,
  });
}

module.exports = {
  ADMIN,
  OPERATOR,
  VALID_IIN,
  INVALID_IIN,
  PHOTO,
  DOC,
  login,
  csrfToken,
  newOperatorRequest,
  addAttendee,
};
