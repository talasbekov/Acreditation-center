import { apiFetch } from './client'

export interface DirectoryRow {
  code: string
  name: string
}

/** Справочники формы участника (этап D) — те же, что у HTML-формы. */
export interface Directories {
  sexes: DirectoryRow[]
  document_types: DirectoryRow[]
  categories: DirectoryRow[]
  countries: DirectoryRow[]
}

/** GET /api/v1/directories/?lang= — только чтение, для оператора; названия на языке интерфейса. */
export function getDirectories(lang = 'ru'): Promise<Directories> {
  return apiFetch<Directories>(`/api/v1/directories/?lang=${encodeURIComponent(lang)}`)
}
