import { forwardRef, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

const base = 'w-full rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm placeholder:text-[var(--muted)] focus-visible:outline-2 disabled:opacity-60'
export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(({ className, ...p }, r) => <input ref={r} className={cn(base, 'h-10', className)} {...p} />)
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...p }, r) => <textarea ref={r} className={cn(base, 'min-h-[88px]', className)} {...p} />)
export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(({ className, children, ...p }, r) => <select ref={r} className={cn(base, 'h-10', className)} {...p}>{children}</select>)
Input.displayName = 'Input'; Textarea.displayName = 'Textarea'; Select.displayName = 'Select'

export function Field({ label, error, hint, children, className }: { label: string; error?: string; hint?: string; children: ReactNode; className?: string }) {
  return (
    <label className={cn('block space-y-1.5', className)}>
      <span className="text-sm font-medium">{label}</span>
      {children}
      {hint && !error && <span className="block text-xs text-[var(--muted)]">{hint}</span>}
      {error && <span role="alert" className="block text-xs text-red-600">{error}</span>}
    </label>
  )
}
export const Check = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { label: string }>(({ label, ...p }, ref) => {
  return <label className="flex items-center gap-2 text-sm cursor-pointer"><input ref={ref} type="checkbox" className="h-4 w-4 accent-[var(--color-forest-700)]" {...p} />{label}</label>
})
Check.displayName = 'Check'
