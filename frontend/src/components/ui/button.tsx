import type { ButtonHTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

// shadcn/ui-style Button. Размер default — h-11 (44px) для anti-fatigue touch target (AC-5).
const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 rounded-md text-base font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      // fe-2.1: варианты на токен-утилитах «Тихий сланец» (var(--…) через @theme inline) —
      // читаются из токенов, переключатся под .dark без правки этого файла.
      variant: {
        default:
          'bg-primary text-primary-foreground hover:bg-primary-hover focus-visible:ring-primary',
        outline:
          'border border-border-strong bg-surface text-text hover:bg-surface-muted',
        ghost: 'text-text hover:bg-surface-muted',
      },
      size: {
        default: 'h-11 px-5 py-2',
        lg: 'h-12 px-6 text-lg',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
)

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants>

export function Button({ className, variant, size, ...props }: ButtonProps) {
  return (
    <button
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  )
}

export { buttonVariants }
