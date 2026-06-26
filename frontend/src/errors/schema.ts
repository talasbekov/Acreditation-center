import { z } from 'zod'

/**
 * Story fe-1.1 — zod-схема DRF-ответа об ошибке (RFC 7807 + машинный код).
 *
 * Сервер отдаёт `{type, field, params, detail}` (api/exceptions.py). `type` — машинный
 * код (errors/registry.py), который React-маппер (fe-1.2) превращает в локализованный
 * текст через `t('errors:'+type, params)`. `detail` — дефолтный язык, ТОЛЬКО логи/не-UI.
 *
 * zod v4: `z.record(keyType, valueType)` требует явный key-type. `field` бывает `null`
 * (напр. permission_denied) → `.nullish()` (string | null | undefined).
 */
export const drfErrorSchema = z.object({
  type: z.string(),
  params: z.record(z.string(), z.unknown()),
  field: z.string().nullish(),
  detail: z.string().nullish(),
})

export type DrfError = z.infer<typeof drfErrorSchema>
