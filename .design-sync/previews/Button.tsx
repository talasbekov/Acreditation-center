import { Button } from 'frontend'

// Варианты на токенах «Тихий сланец»: default (bg-primary), outline, ghost.
export function Variants() {
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
      <Button>Сохранить</Button>
      <Button variant="outline">Отмена</Button>
      <Button variant="ghost">Очистить</Button>
    </div>
  )
}

// h-11 (44px) default — anti-fatigue touch target; lg = h-12.
export function Sizes() {
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
      <Button size="default">Добавить участника</Button>
      <Button size="lg">Отправить на проверку</Button>
    </div>
  )
}

export function Disabled() {
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
      <Button disabled>Сохранить</Button>
      <Button variant="outline" disabled>
        Отмена
      </Button>
    </div>
  )
}
