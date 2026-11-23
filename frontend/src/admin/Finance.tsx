import { useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { api, download, errMsg } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { useAct, useGet } from '@/lib/hooks'
import { Button } from '@/components/ui/button'
import { Field, Input, Select, Textarea } from '@/components/ui/form'
import { Card, CardBody, Modal, PageHeader, Pager, QueryState, StatusBadge, Table, Td, Th } from '@/components/ui/ui'
import { fmtDate, fmtDateTime, money } from '@/lib/utils'

export function Guests() {
  const { can } = useAuth()
  const [q, setQ] = useState(''); const [page, setPage] = useState(1); const [sel, setSel] = useState<string | null>(null); const [add, setAdd] = useState<any>(null)
  const list = useGet(['guests'], '/guests', { q, page, page_size: 20 })
  const det = useGet(['guest', sel], `/guests/${sel}`, undefined, !!sel)
  const [edit, setEdit] = useState<any>({})
  const save = useAct(() => api(`/guests/${sel}`, { method: 'PATCH', body: edit }), { ok: 'Guest updated', invalidate: [['guests'], ['guest']] })
  const create = useAct(() => api('/guests', { body: { name: add.name, email: add.email || null, phone: add.phone ?? '', country: add.country ?? 'Ghana' } }), { ok: 'Guest added', invalidate: [['guests']], onOk: () => setAdd(null) })
  return (<><PageHeader title="Guests" actions={can('guests.manage') && <Button onClick={() => setAdd({})}>Add guest</Button>} />
    <Input className="mb-4 max-w-sm" placeholder="Search name, email or phone" value={q} onChange={(e) => { setQ(e.target.value); setPage(1) }} />
    <QueryState q={list} empty={{ show: list.data?.items.length === 0, text: 'No guests yet.' } as any}>{list.data && <><Table><thead><tr><Th>Name</Th><Th>Phone</Th><Th>Email</Th><Th>Country</Th><Th /></tr></thead><tbody>{list.data.items.map((g: any) => <tr key={g.id}><Td className="font-medium">{g.name}</Td><Td>{g.phone}</Td><Td>{g.email}</Td><Td>{g.country}</Td><Td><Button size="sm" variant="outline" onClick={() => { setSel(g.id); setEdit({}) }}>Open</Button></Td></tr>)}</tbody></Table><Pager page={page} total={list.data.total} pageSize={20} onPage={setPage} /></>}</QueryState>
    <Modal wide open={!!sel} onOpenChange={() => setSel(null)} title={det.data?.name ?? 'Guest'}><QueryState q={det}>{det.data && <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2"><Field label="Name"><Input defaultValue={det.data.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} disabled={!can('guests.manage')} /></Field><Field label="Phone"><Input defaultValue={det.data.phone} onChange={(e) => setEdit({ ...edit, phone: e.target.value })} disabled={!can('guests.manage')} /></Field>
        <Field label="Email"><Input defaultValue={det.data.email} onChange={(e) => setEdit({ ...edit, email: e.target.value })} disabled={!can('guests.manage')} /></Field><Field label="Country"><Input defaultValue={det.data.country} onChange={(e) => setEdit({ ...edit, country: e.target.value })} disabled={!can('guests.manage')} /></Field>
        {can('guests.notes') && <Field label="Internal notes" className="sm:col-span-2"><Textarea defaultValue={det.data.internal_notes} onChange={(e) => setEdit({ ...edit, internal_notes: e.target.value })} /></Field>}</div>
      {can('guests.manage') && <Button loading={save.isPending} disabled={!Object.keys(edit).length} onClick={() => save.mutate(undefined)}>Save changes</Button>}
      <div className="text-sm text-[var(--muted)]">{det.data.total_reservations} reservations · {money(det.data.total_spent_minor)} paid in total</div>
      <Table><thead><tr><Th>Reference</Th><Th>Stay</Th><Th>Status</Th><Th>Paid</Th></tr></thead><tbody>{det.data.reservations.map((r: any) => <tr key={r.id}><Td><Link className="underline" to={`/admin/reservations/${r.id}`}>{r.reference}</Link></Td><Td>{fmtDate(r.check_in)} → {fmtDate(r.check_out)}</Td><Td><StatusBadge status={r.status} /></Td><Td>{money(r.amount_paid)}</Td></tr>)}</tbody></Table></div>}</QueryState></Modal>
    <Modal open={!!add} onOpenChange={() => setAdd(null)} title="Add guest">{add && <div className="space-y-3"><Field label="Name"><Input onChange={(e) => setAdd({ ...add, name: e.target.value })} /></Field><Field label="Phone"><Input onChange={(e) => setAdd({ ...add, phone: e.target.value })} /></Field><Field label="Email"><Input type="email" onChange={(e) => setAdd({ ...add, email: e.target.value })} /></Field><Button loading={create.isPending} disabled={!add.name || add.name.length < 2} onClick={() => create.mutate(undefined)}>Add</Button></div>}</Modal></>)
}

export function Payments() {
  const [f, setF] = useState<any>({}); const [page, setPage] = useState(1)
  const list = useGet(['payments'], '/payments', { ...f, page, page_size: 25 })
  const verify = useAct((id: string) => api(`/payments/${id}/verify`, { method: 'POST' }), { ok: 'Re-verified with Paystack', invalidate: [['payments']] })
  const { can } = useAuth()
  return (<><PageHeader title="Payments" />
    <Card className="mb-4"><CardBody className="grid gap-3 sm:grid-cols-4"><Input placeholder="Reference" onBlur={(e) => { setF({ ...f, q: e.target.value }); setPage(1) }} aria-label="Reference" />
      <Select aria-label="Status" onChange={(e) => setF({ ...f, status: e.target.value })}><option value="">All statuses</option>{['pending', 'success', 'failed', 'abandoned', 'flagged'].map((s) => <option key={s}>{s}</option>)}</Select>
      <Select aria-label="Method" onChange={(e) => setF({ ...f, method: e.target.value })}><option value="">All methods</option>{['paystack', 'cash', 'mobile_money', 'card_pos', 'bank_transfer', 'other'].map((s) => <option key={s}>{s}</option>)}</Select>
      <div className="flex gap-2"><Input type="date" aria-label="From" onChange={(e) => setF({ ...f, date_from: e.target.value })} /><Input type="date" aria-label="To" onChange={(e) => setF({ ...f, date_to: e.target.value })} /></div></CardBody></Card>
    <QueryState q={list} empty={{ show: list.data?.items.length === 0, text: 'No payments.' } as any}>{list.data && <><Table><thead><tr><Th>Date</Th><Th>Reference</Th><Th>Reservation</Th><Th>Method</Th><Th>Status</Th><Th>Amount</Th><Th>Receipt</Th><Th /></tr></thead>
      <tbody>{list.data.items.map((p: any) => <tr key={p.id}><Td>{fmtDateTime(p.created_at)}</Td><Td className="font-mono text-xs">{p.reference}</Td><Td><Link className="underline" to={`/admin/reservations/${p.reservation_id}`}>{p.reservation_reference}</Link></Td><Td>{p.method}</Td><Td><StatusBadge status={p.status} /></Td><Td>{money(p.amount)}</Td><Td>{p.receipt_number ?? '—'}</Td>
        <Td>{p.method === 'paystack' && p.status !== 'success' && can('payments.record') && <Button size="sm" variant="outline" loading={verify.isPending} onClick={() => verify.mutate(p.id)}>Re-verify</Button>}</Td></tr>)}</tbody></Table><Pager page={page} total={list.data.total} pageSize={25} onPage={setPage} /></>}</QueryState></>)
}

export function Refunds() {
  const { can } = useAuth(); const [status, setStatus] = useState(''); const [note, setNote] = useState(''); const [proc, setProc] = useState<any>(null)
  const list = useGet(['refunds'], '/refunds', { status, page_size: 50 }); const inv = [['refunds']] as any
  const approve = useAct((id: string) => api(`/refunds/${id}/approve`, { method: 'POST' }), { ok: 'Approved', invalidate: inv })
  const reject = useAct((id: string) => api(`/refunds/${id}/reject`, { method: 'POST', body: { note: 'Rejected' } }), { ok: 'Rejected', invalidate: inv })
  const process = useAct(() => api(`/refunds/${proc.id}/process`, { method: 'POST', body: { note } }), { ok: 'Refund processing started', invalidate: inv, onOk: () => setProc(null) })
  const m = can('refunds.manage')
  return (<><PageHeader title="Refunds" desc="Refunds are never automatic. Request → approve → process (Paystack refund API for online payments; record manually for cash)." />
    <Select aria-label="Status" className="mb-4 w-48" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All</option>{['requested', 'approved', 'processing', 'processed', 'rejected', 'failed'].map((s) => <option key={s}>{s}</option>)}</Select>
    <QueryState q={list} empty={{ show: list.data?.items.length === 0, text: 'No refunds.' } as any}>{list.data && <Table><thead><tr><Th>Date</Th><Th>Reservation</Th><Th>Reason</Th><Th>Amount</Th><Th>Status</Th><Th /></tr></thead>
      <tbody>{list.data.items.map((r: any) => <tr key={r.id}><Td>{fmtDateTime(r.created_at)}</Td><Td><Link className="underline" to={`/admin/reservations/${r.reservation_id}`}>{r.reservation_reference}</Link></Td><Td>{r.reason}</Td><Td>{money(r.amount)}</Td><Td><StatusBadge status={r.status} /></Td>
        <Td className="space-x-1">{m && r.status === 'requested' && <><Button size="sm" onClick={() => approve.mutate(r.id)}>Approve</Button><Button size="sm" variant="outline" onClick={() => reject.mutate(r.id)}>Reject</Button></>}{m && r.status === 'approved' && <Button size="sm" onClick={() => { setProc(r); setNote('') }}>Process</Button>}</Td></tr>)}</tbody></Table>}</QueryState>
    <Modal open={!!proc} onOpenChange={() => setProc(null)} title="Process refund" desc={proc ? `Refund ${money(proc.amount)} for ${proc.reservation_reference}. Online payments are refunded through Paystack.` : ''}><div className="space-y-3"><Field label="Note"><Input value={note} onChange={(e) => setNote(e.target.value)} /></Field><Button loading={process.isPending} onClick={() => process.mutate(undefined)}>Process refund</Button></div></Modal></>)
}

const REPORTS = [['revenue', 'Revenue', true], ['occupancy', 'Occupancy', false], ['reservations', 'Reservations', false], ['payments', 'Payments', true], ['outstanding', 'Outstanding balances', true], ['cancellations', 'Cancellations', false], ['refunds', 'Refunds', true], ['categories', 'Room category performance', false], ['guests', 'Guests', false]] as const

export function Reports() {
  const { can } = useAuth()
  const [kind, setKind] = useState('occupancy')
  const [start, setStart] = useState(new Date(Date.now() - 29 * 864e5).toISOString().slice(0, 10)); const [end, setEnd] = useState(new Date().toISOString().slice(0, 10)); const [period, setPeriod] = useState('daily')
  const avail = REPORTS.filter(([, , fin]) => !fin || can('reports.financial'))
  const eff = avail.some(([k]) => k === kind) ? kind : avail[0][0]
  const query = { start, end, period: eff === 'revenue' ? period : undefined }
  const q = useGet(['report', eff], `/reports/${eff}`, query)
  const rows: any[] = q.data?.rows ?? []
  const cols: string[] = q.data?.columns ?? (rows[0] ? Object.keys(rows[0]) : [])
  const fmt = (c: string, v: any) => (c.endsWith('_minor') ? money(v) : typeof v === 'number' && /^(total|paid|balance|amount|revenue|avg_rate|refund|fee)/.test(c) ? money(Math.round(v * 100)) : v == null ? '' : String(v))
  const exp = async (format: string) => { try { await download(`/reports/${eff}`, `${eff}-${start}-${end}.${format}`, { ...query, format }) } catch (e) { toast.error(errMsg(e)) } }
  return (<><PageHeader title="Reports" actions={<><Button variant="outline" onClick={() => exp('csv')}>Export CSV</Button><Button variant="outline" onClick={() => exp('xlsx')}>Export Excel</Button></>} />
    <Card className="mb-4"><CardBody className="flex flex-wrap items-end gap-3"><Field label="Report"><Select value={eff} onChange={(e) => setKind(e.target.value)}>{avail.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</Select></Field>
      {eff !== 'outstanding' && <><Field label="From"><Input type="date" value={start} onChange={(e) => setStart(e.target.value)} /></Field><Field label="To"><Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></Field></>}
      {eff === 'revenue' && <Field label="Period"><Select value={period} onChange={(e) => setPeriod(e.target.value)}><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option></Select></Field>}</CardBody></Card>
    <QueryState q={q} empty={{ show: rows.length === 0, text: 'No data for this range.' } as any}>{q.data && <><div className="mb-2 flex flex-wrap gap-4 text-sm">{q.data.totals && Object.entries(q.data.totals).map(([k, v]) => <span key={k}><b>{k.replace(/_/g, ' ')}:</b> {k.endsWith('_minor') ? money(v as number) : String(v)}</span>)}{q.data.average_occupancy_percent !== undefined && <span><b>Average occupancy:</b> {q.data.average_occupancy_percent}%</span>}{q.data.total_balance !== undefined && <span><b>Total outstanding:</b> {money(Math.round(q.data.total_balance * 100))}</span>}</div>
      <Table><thead><tr>{cols.map((c) => <Th key={c}>{c.replace(/_/g, ' ')}</Th>)}</tr></thead><tbody>{rows.slice(0, 500).map((r, i) => <tr key={i}>{cols.map((c) => <Td key={c}>{fmt(c, r[c])}</Td>)}</tr>)}</tbody></Table>{rows.length > 500 && <p className="mt-2 text-xs text-[var(--muted)]">Showing first 500 rows. Export for the full report.</p>}</>}</QueryState></>)
}
