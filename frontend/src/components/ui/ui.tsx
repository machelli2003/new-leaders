import { type HTMLAttributes, type ReactNode } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { AlertCircle, Inbox, Loader2, X } from 'lucide-react'
import { cn, titleCase } from '@/lib/utils'
import { Button } from './button'

export const Card = ({ className, ...p }: HTMLAttributes<HTMLDivElement>) => <div className={cn('rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-sm', className)} {...p} />
export const CardHeader = ({ className, ...p }: HTMLAttributes<HTMLDivElement>) => <div className={cn('flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border)] px-5 py-3.5', className)} {...p} />
export const CardBody = ({ className, ...p }: HTMLAttributes<HTMLDivElement>) => <div className={cn('p-5', className)} {...p} />
export const Skeleton = ({ className }: { className?: string }) => <div className={cn('animate-pulse rounded-md bg-[var(--soft)]', className)} />

const TONES: Record<string, string> = {
  green: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300',
  amber: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
  red: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300',
  blue: 'bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300',
  gray: 'bg-stone-200 text-stone-700 dark:bg-stone-700/50 dark:text-stone-300',
  purple: 'bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-300',
}
export const Badge = ({ tone = 'gray', children, className }: { tone?: keyof typeof TONES; children: ReactNode; className?: string }) =>
  <span className={cn('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap', TONES[tone], className)}>{children}</span>

const STATUS_TONE: Record<string, string> = {
  confirmed: 'green', paid: 'green', success: 'green', processed: 'green', published: 'green', active: 'green', available: 'green', ready: 'green', clean: 'green', done: 'green', checked_out: 'gray',
  pending: 'amber', partially_paid: 'amber', unpaid: 'amber', draft: 'amber', requested: 'amber', approved: 'blue', processing: 'blue', open: 'amber', in_progress: 'blue', cleaning: 'blue', inspection: 'purple', hold: 'amber',
  checked_in: 'blue', occupied: 'blue', reserved: 'purple', refund_pending: 'purple', partially_refunded: 'purple', refunded: 'gray',
  failed: 'red', cancelled: 'red', no_show: 'red', expired: 'gray', cancellation_requested: 'red', flagged: 'red', rejected: 'red', dirty: 'red', maintenance: 'red', out_of_service: 'red', archived: 'gray', abandoned: 'gray', urgent: 'red', high: 'amber', normal: 'gray', low: 'gray',
}
export const StatusBadge = ({ status }: { status?: string | null }) => status ? <Badge tone={(STATUS_TONE[status] as any) ?? 'gray'}>{titleCase(status)}</Badge> : null

export function PageHeader({ title, desc, actions }: { title: string; desc?: string; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0 flex-1"><h1 className="break-words text-2xl font-semibold">{title}</h1>{desc && <p className="mt-1 break-words text-sm text-[var(--muted)]">{desc}</p>}</div>
      <div className="flex flex-wrap gap-2">{actions}</div>
    </div>
  )
}

export function QueryState({ q, children, empty }: { q: { isLoading: boolean; isError: boolean; error: unknown; refetch: () => void; data: any }; children: ReactNode; empty?: { show: boolean; text: string } }) {
  if (q.isLoading) return <div className="space-y-3"><Skeleton className="h-10" /><Skeleton className="h-10" /><Skeleton className="h-10" /></div>
  if (q.isError) return (
    <div className="flex flex-col items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-8 text-center text-sm text-red-700 dark:bg-red-950/30 dark:border-red-900">
      <AlertCircle className="h-6 w-6" />{(q.error as Error)?.message ?? 'Failed to load'}<Button size="sm" variant="outline" onClick={() => q.refetch()}>Retry</Button>
    </div>)
  if (empty?.show) return <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-[var(--border)] p-10 text-center text-sm text-[var(--muted)]"><Inbox className="h-6 w-6" />{empty.text}</div>
  return <>{children}</>
}

export function Modal({ open, onOpenChange, title, desc, children, wide }: { open: boolean; onOpenChange: (o: boolean) => void; title: string; desc?: string; children: ReactNode; wide?: boolean }) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50" />
        <Dialog.Content className={cn('admin-ui fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-[95vw] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-xl', wide ? 'max-w-3xl' : 'max-w-lg')}>
          <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
            <div><Dialog.Title className="text-lg font-semibold">{title}</Dialog.Title>{desc && <Dialog.Description className="mt-1 text-sm text-[var(--muted)]">{desc}</Dialog.Description>}</div>
            <Dialog.Close className="rounded p-1 hover:bg-[var(--soft)]" aria-label="Close"><X className="h-4 w-4" /></Dialog.Close>
          </div>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

export function Confirm({ open, onOpenChange, title, desc, confirmLabel = 'Confirm', danger, onConfirm, loading }: { open: boolean; onOpenChange: (o: boolean) => void; title: string; desc: ReactNode; confirmLabel?: string; danger?: boolean; onConfirm: () => void; loading?: boolean }) {
  return (
    <Modal open={open} onOpenChange={onOpenChange} title={title}>
      <div className="text-sm text-[var(--muted)]">{desc}</div>
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
        <Button variant={danger ? 'destructive' : 'default'} loading={loading} onClick={onConfirm}>{confirmLabel}</Button>
      </div>
    </Modal>
  )
}

export function Table({ children }: { children: ReactNode }) {
  return <div className="overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--card)]"><table className="w-full text-left text-sm">{children}</table></div>
}
export const Th = ({ children, className }: { children?: ReactNode; className?: string }) => <th className={cn('whitespace-nowrap border-b border-[var(--border)] bg-[var(--soft)] px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]', className)}>{children}</th>
export const Td = ({ children, className, ...p }: HTMLAttributes<HTMLTableCellElement>) => <td className={cn('border-b border-[var(--border)] px-4 py-3 align-middle last:border-0', className)} {...p}>{children}</td>

export function Pager({ page, total, pageSize, onPage }: { page: number; total: number; pageSize: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  return (
    <div className="mt-3 flex items-center justify-between text-sm text-[var(--muted)]">
      <span>{total} result{total === 1 ? '' : 's'}</span>
      <div className="flex items-center gap-2"><Button size="sm" variant="outline" disabled={page <= 1} onClick={() => onPage(page - 1)}>Prev</Button>
        <span>Page {page} / {pages}</span><Button size="sm" variant="outline" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</Button></div>
    </div>
  )
}
export const Spinner = () => <Loader2 className="h-5 w-5 animate-spin" />
export const Stat = ({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: string; tone?: string }) => (
  <Card className="p-4"><div className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">{label}</div><div className={cn('mt-1 text-2xl font-semibold', tone)}>{value}</div>{sub && <div className="mt-0.5 text-xs text-[var(--muted)]">{sub}</div>}</Card>
)
