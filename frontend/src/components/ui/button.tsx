import type { ButtonHTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

// shadcn/ui-style Button. Размер default — h-11 (44px) для anti-fatigue touch target (AC-5).
const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 rounded-md text-base font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default:
          'bg-blue-700 text-white hover:bg-blue-800 focus-visible:ring-blue-700',
        outline:
          'border border-neutral-400 bg-white text-neutral-900 hover:bg-neutral-100',
        ghost: 'text-neutral-900 hover:bg-neutral-100',
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
