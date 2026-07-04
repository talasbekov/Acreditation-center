// design-sync barrel: единственный вход конвертера claude.ai/design (см. .design-sync/NOTES.md).
// Экспортирует РОВНО те компоненты, что уезжают в Design System проект — не app-wiring
// (main.tsx/RequireAuth/pages сюда не входят). tsconfig.dstypes.json эмитит из этого файла
// .d.ts-дерево (.ds-types/) — контракт props для дизайн-агента.
export { Button, buttonVariants, type ButtonProps } from './src/components/ui/button'
export { StatusBadge } from './src/components/StatusBadge'
export { LanguageSwitcher } from './src/components/LanguageSwitcher'
export { ReturnReasonDialog } from './src/components/ReturnReasonDialog'
export { UploadZone, type UploadZoneProps } from './src/components/upload/UploadZone'
export { DocumentUpload, type DocumentUploadProps } from './src/components/DocumentUpload/DocumentUpload'
export { PhotoUpload, type PhotoUploadProps } from './src/components/PhotoUpload/PhotoUpload'
export { AppShell } from './src/components/shell/AppShell'
export { AttendeeForm, type AttendeeFormProps } from './src/components/AttendeeForm'
export { ThemeProvider, useTheme, type Theme } from './src/providers/ThemeProvider'
