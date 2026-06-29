# 🚩 KZ catalog — NEEDS NATIVE + LEGAL REVIEW (Story fe-1.4)

**Status:** `needs-native-review` — Kazakh strings were written **best-effort by the
implementation agent (not a native speaker)**. They are structurally complete (every `ru`
key has a `kz` counterpart) and tofu-free, but the wording is **not yet validated**.

## Who must review

A native Kazakh speaker **with legal/compliance authority** (госязык requirement). The IIN
(ЖСН) validation messages and auth/access messages are legally meaningful.

## What to review

1. **`validation.json`** — ИИН/ЖСН validation messages (legal). Especially:
   `iin_format`, `iin_control`, `iin_date`, `iin_dob_mismatch`, `iin_required_resident`.
2. **`common.json`** — auth/access messages (`attendee.*`, `auth.*`), list/table UI,
   pagination word order (`pagination.showing`).
3. **`operatorForm.json`** — form field labels, country options, draft banner, upload
   instructions, toasts.
4. **`status.json` / `nav.json`** — status labels and navigation labels.

## NOT to localize (verify these stay verbatim)

- Person **ФИО / names / transliteration** (data values, never localized).
- **ИИН / ЖСН digits** (the numeric value; only the *label* is localized: `ru "ИИН"` → `kz "ЖСН"`).
- **`PDF`** acronym.

## After review (procedure)

1. Apply corrections to `kz/*.json`.
2. Recompute the catalog hash:
   `node -e "import('./scripts/check-kz-review.mjs').then(m => console.log(m.computeCatalogHash(new URL('./src/locales/kz', 'file://'+process.cwd()+'/').pathname)))"`
   (or just run `npm run lint:kz-review`, which prints the current hash).
3. Update `.review-record.json`: set `reviewer` (role/ФИО), `date` (ISO date), and
   `catalog_hash` to the freshly computed value.
4. Once `date !== null`, the `lint:kz-review` gate becomes **blocking**: any later drift in
   `kz/*.json` (hash mismatch) fails CI until re-reviewed.
