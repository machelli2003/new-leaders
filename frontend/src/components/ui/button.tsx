import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

const variants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 cursor-pointer',
  {
    variants: {
      variant: {
        default: 'bg-forest-700 text-white hover:bg-forest-800',
        gold: 'bg-gold-500 text-white hover:bg-gold-600',
        outline: 'border border-[var(--border)] bg-[var(--card)] hover:bg-[var(--soft)]',
        ghost: 'hover:bg-[var(--soft)]',
        destructive: 'bg-red-600 text-white hover:bg-red-700',
        link: 'text-forest-600 underline-offset-4 hover:underline p-0 h-auto',
      },
      size: { default: 'h-10 px-4 py-2', sm: 'h-8 px-3 text-xs', lg: 'h-12 px-7 text-base', icon: 'h-9 w-9' },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
)
type Props = ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof variants> & { asChild?: boolean; loading?: boolean }
export const Button = forwardRef<HTMLButtonElement, Props>(({ className, variant, size, asChild, loading, children, disabled, ...p }, ref) => {
  const Comp: any = asChild ? Slot : 'button'
  return (
    <Comp ref={ref} className={cn(variants({ variant, size }), className)} disabled={disabled || loading} {...p}>
      {asChild ? children : <>{loading && <Loader2 className="h-4 w-4 animate-spin" />}{children}</>}
    </Comp>
  )
})
Button.displayName = 'Button'
