import { ReturnReasonDialog } from 'frontend'

// Модалка возврата заявки с обязательной причиной (fe-3.5): focus-trap, Esc, scrim
// bg-overlay. Диалог рендерится через `fixed inset-0` — в карточке ему нужен
// containing block с реальной высотой: transform:translateZ(0) делает обёртку
// опорной для fixed, высота ~592px заполняет viewport карточки (640 − отступы).
export function Open() {
  return (
    <div style={{ transform: 'translateZ(0)', height: 592, position: 'relative', overflow: 'hidden' }}>
      <ReturnReasonDialog open onClose={() => {}} onSubmit={() => {}} />
    </div>
  )
}
