// Story fe-2.1 (AC-3): токен-lint. Запрещает сырые цвета / light-only-хардкоды вне
// токен-слоя, чтобы компоненты шли через токены (дешёвый дефер тёмной темы).
// oxlint CSS не умеет, stylelint в проекте нет → свой zero-dep чек по коду/CSS.
import { readdirSync, readFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const HEX = /#[0-9a-fA-F]{3,8}\b/g
// light-only Tailwind-хардкоды: ломают тёмную тему (нет токена). `(?<!dark:)` — НЕ флагать
// легитимный `dark:bg-white` (белый только в тёмной теме, появится с fe-2.3).
const LIGHT_ONLY_CLASS = /(?<!dark:)\b(?:bg-white|bg-black|text-black)\b/g
const SCAN_EXT = /\.(tsx?|jsx?|mjs|cjs|mts|cts|css)$/
const CODE_EXT = /\.(tsx?|jsx?|mjs|cjs|mts|cts)$/

/** Блокирует hex в комментариях (ложные срабатывания на `// old color #fff`), сохраняя
 *  номера строк/колонок (замена символов комментария на пробелы). Строки НЕ трогаем —
 *  цвет-литерал `'#fff'` в style должен ловиться. `//` стрипаем только в коде (в CSS
 *  его нет, а `url(http://…)` содержит `//`). */
function stripComments(content, isCode) {
  let s = content.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
  if (isCode) s = s.replace(/\/\/[^\n]*/g, (m) => ' '.repeat(m.length))
  return s
}

/**
 * Нарушения для одного файла. `relPath` — путь от корня frontend (norm slashes).
 * Сырой hex разрешён ТОЛЬКО в самом токен-файле src/index.css (точное совпадение).
 * Light-only-классы проверяются в коде (.ts/.tsx/.js/…).
 */
export function findViolations(relPath, content) {
  const norm = relPath.replace(/\\/g, '/')
  const isTokenFile = norm === 'src/index.css'
  const isCode = CODE_EXT.test(norm)
  const scanned = stripComments(content, isCode)
  const out = []
  scanned.split('\n').forEach((lineText, i) => {
    if (!isTokenFile) {
      for (const m of lineText.matchAll(HEX)) {
        out.push({ line: i + 1, col: (m.index ?? 0) + 1, rule: 'no-raw-hex', text: m[0] })
      }
    }
    if (isCode) {
      for (const m of lineText.matchAll(LIGHT_ONLY_CLASS)) {
        out.push({ line: i + 1, col: (m.index ?? 0) + 1, rule: 'no-light-only-class', text: m[0] })
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
    if (ent.name === 'node_modules' || ent.name === 'dist') continue
    if (ent.isSymbolicLink()) continue // не следуем симлинкам (циклы/битые ссылки)
    const p = join(dir, ent.name)
    if (ent.isDirectory()) files.push(...walk(p))
    else if (ent.isFile() && SCAN_EXT.test(ent.name)) files.push(p)
  }
  return files
}

function main() {
  const srcDir = fileURLToPath(new URL('../src', import.meta.url))
  const repoRoot = fileURLToPath(new URL('..', import.meta.url))
  const problems = []
  for (const file of walk(srcDir)) {
    const rel = relative(repoRoot, file).replace(/\\/g, '/')
    for (const v of findViolations(rel, readFileSync(file, 'utf8'))) {
      problems.push(`${rel}:${v.line}:${v.col}  [${v.rule}] ${v.text}`)
    }
  }
  if (problems.length) {
    console.error(
      `token-lint: найдены сырые цвета / light-only-хардкоды (используйте токены):\n${problems.join('\n')}`,
    )
    process.exit(1)
  }
  console.log('token-lint: OK')
}

// Запуск main() только при прямом вызове `node scripts/lint-tokens.mjs` (не при импорте в тест).
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main()
}
