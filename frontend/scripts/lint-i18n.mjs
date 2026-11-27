// Story fe-1.4 (AC-1): i18n-lint. Запрещает хардкод-строки на кириллице в коде вне
// слоя каталогов локалей. Все видимые строки должны идти через `t('namespace:key')`,
// а тексты жить в `src/locales/**`. oxlint этого не умеет → свой zero-dep чек по коду
// (тот же паттерн, что lint-tokens.mjs).
import { readdirSync, readFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const SCAN_EXT = /\.(tsx?)$/
// Тесты/спеки исключаем — там кириллица в фикстурах/ассертах легитимна.
const TEST_EXT = /\.(test|spec)\.(tsx?)$/
// Полный кириллический блок U+0400–U+04FF — покрывает и казахские буквы (ә/ғ/қ/ң/ө/ұ/ү/һ/і),
// не только русские (review fe-1.4: А-Яа-яёЁ пропускал kz-специфичные глифы).
const CYRILLIC = /[Ѐ-ӿ]/
// Кириллический строковый литерал: кавычка, текст без кавычек, ≥1 кириллическая буква.
const CYRILLIC_LITERAL = /(['"`])[^'"`]*[Ѐ-ӿ][^'"`]*\1/g
// Голый JSX-текст: `>…кириллица…<` (самый частый React-вектор; кавычки-литералы его не ловят).
// `[^<>{}]` исключает вложенные теги / JSX-выражения {…} / сравнения — минимум ложняка.
const CYRILLIC_JSX_TEXT = />[^<>{}]*[Ѐ-ӿ][^<>{}]*</g
// Токены, которым разрешено оставаться кириллицей (доменные аббревиатуры). Строка
// допускается ТОЛЬКО если после удаления whitelisted-токенов кириллицы не осталось.
const WHITELIST = ['ИИН', 'ФИО']

// Блокирует кириллицу в комментариях (line и block), сохраняя номера строк/колонок
// (замена символов комментария на пробелы). Строковые литералы НЕ трогаем — иначе
// кириллический литерал внутри строки не поймался бы.
function stripComments(content) {
  let s = content.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
  s = s.replace(/\/\/[^\n]*/g, (m) => ' '.repeat(m.length))
  return s
}

/** Остаётся ли кириллица в тексте после удаления whitelisted-токенов. */
function cyrillicRemains(text) {
  let inner = text
  for (const token of WHITELIST) inner = inner.split(token).join('')
  return CYRILLIC.test(inner)
}

/** Содержит ли литерал кириллицу ВНЕ whitelisted-токенов (снимаем кавычки). */
function hasNonWhitelistedCyrillic(literal) {
  return cyrillicRemains(literal.slice(1, -1))
}

/**
 * Нарушения для одного файла. `relPath` — путь от корня frontend (norm slashes).
 * Каталоги локалей (`src/locales/**`) и тесты не сканируются (отсев в walk/main).
 */
export function findViolations(relPath, content) {
  const scanned = stripComments(content)
  const out = []
  scanned.split('\n').forEach((lineText, i) => {
    for (const m of lineText.matchAll(CYRILLIC_LITERAL)) {
      if (hasNonWhitelistedCyrillic(m[0])) {
        out.push({ line: i + 1, col: (m.index ?? 0) + 1, rule: 'no-cyrillic-literal', text: m[0] })
      }
    }
    // Голый JSX-текст (`>…кириллица…<`) — вне кавычек, литеральный чек его не видит.
    for (const m of lineText.matchAll(CYRILLIC_JSX_TEXT)) {
      const inner = m[0].slice(1, -1) // снимаем '>' и '<'
      if (cyrillicRemains(inner)) {
        out.push({ line: i + 1, col: (m.index ?? 0) + 1, rule: 'no-cyrillic-jsx-text', text: m[0] })
      }
    }
  })
  return out
}

function walk(dir) {
  const files = []
  let entries
  try {
    entries = readdirSync(dir, { withFileTypes: true })
  } catch {
    return files // отсутствующая/нечитаемая директория — пропускаем, не валимся
  }
  for (const ent of entries) {
    if (ent.name === 'node_modules' || ent.name === 'dist' || ent.name === 'locales') continue
    if (ent.isSymbolicLink()) continue // не следуем симлинкам (циклы/битые ссылки)
    const p = join(dir, ent.name)
    if (ent.isDirectory()) files.push(...walk(p))
    else if (ent.isFile() && SCAN_EXT.test(ent.name) && !TEST_EXT.test(ent.name)) files.push(p)
  }
  return files
}

function main() {
  const srcDir = fileURLToPath(new URL('../src', import.meta.url))
  const repoRoot = fileURLToPath(new URL('..', import.meta.url))
  const problems = []
  for (const file of walk(srcDir)) {
    const rel = relative(repoRoot, file).replace(/\\/g, '/')
    if (rel.startsWith('src/locales/')) continue
    for (const v of findViolations(rel, readFileSync(file, 'utf8'))) {
      problems.push(`${rel}:${v.line}:${v.col}  [${v.rule}] ${v.text}`)
    }
  }
  if (problems.length) {
    console.error(
      `i18n-lint: найдены хардкод-строки на кириллице (вынесите в src/locales/** через t('ns:key')):\n${problems.join('\n')}`,
    )
    process.exit(1)
  }
  console.log('i18n-lint: OK')
}

// Запуск main() только при прямом вызове (не при импорте в тест).
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main()
}
