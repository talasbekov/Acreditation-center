// Story fe-1.4 (AC-4): kz — юридический gate. Агент НЕ носитель языка → kz-каталог
// заполнен best-effort и ДОЛЖЕН пройти native+legal review до релиза. Этот скрипт —
// «гейт, который не протухает молча»:
//   - date === null (ещё не отревьюено) → WARN, exit 0 (не блокируем первичный мердж
//     этой стори — kz объективно не может быть отревьюен в момент её мерджа);
//   - date !== null И hash kz-каталогов разошёлся с зафиксированным в review-record →
//     FAIL, exit 1 (kz изменили ПОСЛЕ ревью — нужен повторный review);
//   - date !== null И hash совпадает → OK, exit 0.
// Хэш — sha256 от конкатенации отсортированных по имени kz/*.json (без .review-record.json).
import { createHash } from 'node:crypto'
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

/**
 * sha256 (hex) от конкатенации содержимого kz-каталогов (отсортированы по имени;
 * dot-файлы, в т.ч. .review-record.json, исключены — иначе хэш зависел бы от себя).
 */
export function computeCatalogHash(
  kzDir,
  list = (d) => readdirSync(d),
  read = (p) => readFileSync(p, 'utf8'),
) {
  const files = list(kzDir)
    .filter((f) => f.endsWith('.json') && !f.startsWith('.'))
    .sort()
  const hash = createHash('sha256')
  for (const f of files) hash.update(read(join(kzDir, f)))
  return hash.digest('hex')
}

/**
 * Чистое решение гейта (тестируемо без файловой системы).
 * @returns {{ status: 'ok'|'warn'|'fail', exitCode: 0|1, message: string }}
 */
export function evaluateReview(currentHash, record) {
  if (!record || !record.date) {
    // !record.date ловит null/undefined И falsy-мусор ('', 0, false) → трактуем как «не отревьюено».
    return {
      status: 'warn',
      exitCode: 0,
      message:
        'kz-review: каталог НЕ отревьюен (date:null). Предупреждение — dev-гейт не блокируется. ' +
        'До релиза требуется native+legal review (см. src/locales/kz/REVIEW.md).',
    }
  }
  if (record.catalog_hash !== currentHash) {
    return {
      status: 'fail',
      exitCode: 1,
      message:
        `kz-review: kz-каталог ИЗМЕНЁН после ревью (${record.date}). ` +
        'Требуется повторный native+legal review, затем обновить .review-record.json.',
    }
  }
  return { status: 'ok', exitCode: 0, message: `kz-review: OK (отревьюено ${record.date}, hash совпадает).` }
}

function main() {
  const kzDir = fileURLToPath(new URL('../src/locales/kz', import.meta.url))
  const recordPath = join(kzDir, '.review-record.json')
  // Различаем «файла нет» (первый мердж — record=null→warn) и «файл есть, но битый JSON»
  // (подозрительно: мог быть отревьюен и повреждён → fail-loud, гейт не деградирует молча).
  let raw = null
  try {
    raw = readFileSync(recordPath, 'utf8')
  } catch {
    raw = null // файл отсутствует
  }
  let record = null
  if (raw !== null) {
    try {
      record = JSON.parse(raw)
    } catch {
      console.error(
        'kz-review: .review-record.json присутствует, но НЕ парсится (повреждён). ' +
          'Гейт не деградирует молча — восстановите review-record. FAIL.',
      )
      process.exit(1)
    }
  }
  const currentHash = computeCatalogHash(kzDir)
  const res = evaluateReview(currentHash, record)
  if (res.status === 'fail') {
    console.error(`${res.message}\n  ожидался hash: ${record?.catalog_hash}\n  текущий hash:  ${currentHash}`)
    process.exit(1)
  }
  if (res.status === 'warn') {
    console.warn(`${res.message}\n  текущий hash: ${currentHash}`)
    process.exit(0)
  }
  console.log(res.message)
}

// Запуск main() только при прямом вызове (не при импорте в тест).
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main()
}
