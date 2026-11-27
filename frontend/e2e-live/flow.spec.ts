// Этап E (п. 4): сквозной сценарий «браузер → Django → PostgreSQL → хранилище файлов».
// Без подмены API: настоящий Django на базе e2e, SPA через Vite, синтетические данные.
import { test, expect, type Page } from '@playwright/test'
import { readFileSync, mkdirSync } from 'node:fs'
import { join } from 'node:path'

const E2E = process.env.E2E_DIR as string
const creds = JSON.parse(readFileSync(join(E2E, 'creds.json'), 'utf-8'))
// Порты можно сменить, если 18811/18812 заняты другим стендом.
const SPA = process.env.E2E_SPA_URL || 'http://127.0.0.1:18812'
const DJANGO = process.env.E2E_DJANGO_URL || 'http://127.0.0.1:18811'
const SURNAME = 'Сквозной'
const OUT = join(E2E, 'out')
mkdirSync(OUT, { recursive: true })

async function login(page: Page, base: string, next: string, who: { username: string; password: string }) {
  await page.goto(`${base}/user_login/?next=${encodeURIComponent(next)}`)
  await page.getByLabel('Логин').fill(who.username)
  await page.getByLabel('Пароль').fill(who.password)
  await page.getByRole('button', { name: 'Войти' }).click()
}

test('оператор добавляет и отправляет, проверяющий допускает, выгрузка содержит участника', async ({ browser }) => {
  test.setTimeout(120_000)

  // 1. Оператор: вход через Django-форму, возврат в SPA.
  const opCtx = await browser.newContext()
  const op = await opCtx.newPage()
  await login(op, SPA, '/', creds.operator)
  await expect(op.getByRole('heading', { name: 'Участники' })).toBeVisible()

  // 2. Добавление со всеми полями HTML-формы и реальными файлами (фото JPG, скан PDF).
  await op.getByRole('button', { name: 'Добавить участника' }).click()
  await expect(op.getByRole('heading', { name: 'Добавить участника' })).toBeVisible()
  await expect(op.getByRole('option', { name: 'Мужской' })).toBeAttached()
  await op.getByLabel('Фамилия').fill(SURNAME)
  await op.getByLabel('Имя', { exact: true }).fill('Тест')
  await op.getByLabel('Имя латиницей').fill('SKVOZNOY TEST')
  await op.getByLabel('Дата рождения').fill('1990-05-15')
  await op.getByLabel('Пол').selectOption('1')
  await op.getByLabel('Должность').fill('Инженер')
  await op.getByLabel('ИИН', { exact: true }).fill('900515312349')
  await op.getByLabel('Тип документа').selectOption('1000000001')
  await op.getByLabel('Номер документа').fill('E2E-0001')
  await op.getByLabel('Дата выдачи').fill('2020-01-01')
  await op.getByLabel('Действителен до').fill('2034-01-01')
  await op.getByLabel('Заявка', { exact: true }).selectOption({ label: 'E2E-01 — Сквозное мероприятие' })
  await op.getByLabel('Объекты посещения').fill('Зал А')
  await op.getByLabel(/Фото участника/).setInputFiles(join(E2E, 'files', 'photo.jpg'))
  await op.getByLabel(/Скан документа/).setInputFiles(join(E2E, 'files', 'scan.pdf'))
  await op.getByRole('button', { name: 'Сохранить', exact: true }).click()
  await expect(op.getByText('Участник добавлен')).toBeVisible({ timeout: 20_000 })

  // 3. Реестр: поиск, карточка, превью файлов с сервера, отправка на проверку.
  await op.getByRole('link', { name: /К списку участников/ }).click()
  await op.getByLabel('Поиск по ФИО').fill(SURNAME)
  await op.getByRole('link', { name: new RegExp(SURNAME) }).click()
  await expect(op.getByAltText(/Текущее: Фото участника/)).toBeVisible()
  await expect(op.getByAltText(/Текущее: Скан документа/)).toBeVisible()
  // Превью приходит с сервера (защищённый /media/): картинка действительно загрузилась.
  for (const alt of [/Текущее: Фото участника/, /Текущее: Скан документа/]) {
    await expect
      .poll(() => op.getByAltText(alt).evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth))
      .toBeGreaterThan(0)
  }
  await op.getByRole('button', { name: 'Отправить на проверку' }).click()
  await expect(op.getByText('Отправлен на проверку').first()).toBeVisible()
  await op.screenshot({ path: join(OUT, 'operator-card-sent.png'), fullPage: true })

  // 4. Проверяющий: очередь, «Взять на проверку», «Допустить».
  const revCtx = await browser.newContext({ acceptDownloads: true })
  const rev = await revCtx.newPage()
  await login(rev, DJANGO, `/review/${creds.event}/`, creds.superoperator)
  await expect(rev.getByRole('heading', { name: 'Очередь проверки' })).toBeVisible()
  const card = rev.getByRole('article').filter({ hasText: SURNAME })
  await expect(card.getByRole('img', { name: /Фото участника/ })).toBeVisible()
  await card.getByRole('button', { name: 'Взять на проверку' }).click()
  await expect(rev.getByText(/взят\(а\) на проверку/)).toBeVisible()
  await rev.getByRole('article').filter({ hasText: SURNAME }).getByRole('button', { name: 'Допустить' }).click()
  await expect(rev.getByText('Нет участников, ожидающих проверки.')).toBeVisible()

  // 5. Дашборд: выгрузка новых записей заявки — пакет сохраняется для проверки состава.
  await rev.goto(`${DJANGO}/dashboard/${creds.event}/`)
  const [download] = await Promise.all([
    rev.waitForEvent('download'),
    rev.getByRole('button', { name: 'Скачать новые записи' }).click(),
  ])
  await download.saveAs(join(OUT, 'export.zip'))
  await rev.reload()
  await expect(rev.getByText('Приём не подтверждён')).toBeVisible()
  await rev.screenshot({ path: join(OUT, 'dashboard-after-export.png'), fullPage: true })

  // 6. Оператор видит итоговый статус; реестр на телефоне без горизонтальной прокрутки.
  await op.goto(`${SPA}/`)
  await op.getByLabel('Поиск по ФИО').fill(SURNAME)
  await expect(op.getByRole('table').getByText('Допущен, передан в службу')).toBeVisible()
  await op.setViewportSize({ width: 390, height: 844 })
  const widths = await op.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth])
  expect(widths[0]).toBeLessThanOrEqual(widths[1])
  await op.screenshot({ path: join(OUT, 'operator-registry-390.png') })

  await opCtx.close()
  await revCtx.close()
})
