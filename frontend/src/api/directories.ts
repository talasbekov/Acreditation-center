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

/** GET /api/v1/directories/ — только чтение, для оператора. */
export function getDirectories(): Promise<Directories> {
  return apiFetch<Directories>('/api/v1/directories/')
}
