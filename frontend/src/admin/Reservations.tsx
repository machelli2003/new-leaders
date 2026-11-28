import { useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { Plus, Printer } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { useAct, useGet } from '@/lib/hooks'
import { Button } from '@/components/ui/button'
import { Field, Input, Select, Textarea } from '@/components/ui/form'
import { Card, CardBody, CardHeader, Confirm, Modal, PageHeader, Pager, QueryState, Table, Td, Th, StatusBadge } from '@/components/ui/ui'
import { fmtDate, fmtDateTime, fromMinor, money, toMinor } from '@/lib/utils'

const STATUSES = ['pending', 'confirmed', 'checked_in', 'checked_out', 'cancelled', 'cancellation_requested', 'no_show', 'expired']

export function Reservations() {
  const [sp, setSp] = useSearchParams()
  const { can } = useAuth()
  const page = Number(sp.get('page') ?? 1)
  const f = { q: sp.get('q') ?? '', status: sp.get('status') ?? '', payment_status: sp.get('payment_status') ?? '', check_in_from: sp.get('from') ?? '', check_in_to: sp.get('to') ?? '' }
  const set = (k: string, v: string) => { const n = new URLSearchParams(sp); v ? n.set(k, v) : n.delete(k); n.delete('page'); setSp(n) }
  const q = useGet(['reservations'], '/reservations', { ...f, page, page_size: 20 })
  return (<><PageHeader title="Reservations" actions={can('reservations.create') && <Button asChild><Link to="/admin/reservations/new"><Plus className="h-4 w-4" />New reservation</Link></Button>} />
    <Card className="mb-4"><CardBody className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      <Input placeholder="Reference, guest, phone, email" defaultValue={f.q} onKeyDown={(e) => e.key === 'Enter' && set('q', (e.target as HTMLInputElement).value)} onBlur={(e) => set('q', e.target.value)} aria-label="Search" />
      <Select aria-label="Status" value={f.status} onChange={(e) => set('status', e.target.value)}><option value="">All statuses</option>{STATUSES.map((s) => <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>)}</Select>
      <Select aria-label="Payment" value={f.payment_status} onChange={(e) => set('payment_status', e.target.value)}><option value="">All payments</option>{['unpaid', 'partially_paid', 'paid', 'refunded', 'partially_refunded'].map((s) => <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>)}</Select>
      <Input type="date" aria-label="Check-in from" value={f.check_in_from} onChange={(e) => set('from', e.target.value)} /><Input type="date" aria-label="Check-in to" value={f.check_in_to} onChange={(e) => set('to', e.target.value)} /></CardBody></Card>
    <QueryState q={q} empty={{ show: q.data?.items.length === 0, text: 'No reservations match.' } as any}>{q.data && <><Table><thead><tr><Th>Reference</Th><Th>Guest</Th><Th>Stay</Th><Th>Rooms</Th><Th>Status</Th><Th>Payment</Th><Th>Total</Th><Th>Balance</Th></tr></thead>
      <tbody>{q.data.items.map((r: any) => <tr key={r.id} className="hover:bg-[var(--soft)]"><Td><Link className="font-medium text-[var(--primary)] underline" to={`/admin/reservations/${r.id}`}>{r.reference}</Link>{r.needs_attention && <span title="Needs attention" className="ml-1 text-amber-600">⚠</span>}</Td><Td>{r.guest?.name}</Td><Td>{fmtDate(r.check_in)} → {fmtDate(r.check_out)}</Td><Td>{r.rooms_count}</Td><Td><StatusBadge status={r.status} /></Td><Td><StatusBadge status={r.payment_status} /></Td><Td>{money(r.total_amount)}</Td><Td>{money(r.balance)}</Td></tr>)}</tbody></Table>
      <Pager page={page} total={q.data.total} pageSize={20} onPage={(p) => { const n = new URLSearchParams(sp); n.set('page', String(p)); setSp(n) }} /></>}</QueryState></>)
}

export function NewReservation() {
  const nav = useNavigate()
  const [v, setV] = useState({ check_in: '', check_out: '', adults: 2, children: 0, name: '', email: '', phone: '', country: 'Ghana', special_requests: '', internal_notes: '', source: 'walk_in', status: 'confirmed', promo_code: '' })
  const [sel, setSel] = useState<Record<string, number>>({})
  const [rooms, setRooms] = useState<Record<string, string>>({})
  const ok = v.check_in && v.check_out && v.check_out > v.check_in
  const cats = useGet(['cats'], '/room-categories')
  const avail = useGet(['freeRooms', v.check_in, v.check_out], '/availability/rooms', { check_in: v.check_in, check_out: v.check_out }, !!ok)
  const picks = Object.entries(sel).filter(([, n]) => n > 0)
  const create = useAct(() => api<any>('/reservations', { body: { check_in: v.check_in, check_out: v.check_out, adults: Number(v.adults), children: Number(v.children),
    selections: picks.map(([category_id, quantity]) => ({ category_id, quantity, room_ids: rooms[category_id] ? [rooms[category_id]] : [] })),
    guest: { name: v.name, email: v.email || null, phone: v.phone, country: v.country }, special_requests: v.special_requests, internal_notes: v.internal_notes, promo_code: v.promo_code || null, status: v.status, source: v.source } }),
    { ok: 'Reservation created', onOk: (r) => nav(`/admin/reservations/${r.reservation?.id ?? r.id}`) })
  const s = (k: string) => ({ value: (v as any)[k], onChange: (e: any) => setV({ ...v, [k]: e.target.value }) })
  const list = (cats.data?.items ?? cats.data ?? []) as any[]
  return (<><PageHeader title="New reservation" desc="Walk-in, phone or manual booking" />
    <div className="grid gap-4 lg:grid-cols-2">
      <Card><CardHeader><h3 className="font-semibold">Stay</h3></CardHeader><CardBody className="grid gap-3 sm:grid-cols-2">
        <Field label="Check-in"><Input type="date" {...s('check_in')} /></Field><Field label="Check-out"><Input type="date" {...s('check_out')} /></Field>
        <Field label="Adults"><Input type="number" min={1} {...s('adults')} /></Field><Field label="Children"><Input type="number" min={0} {...s('children')} /></Field>
        <Field label="Source"><Select {...s('source')}><option value="walk_in">Walk-in</option><option value="phone">Phone</option><option value="staff">Staff</option></Select></Field>
        <Field label="Status"><Select {...s('status')}><option value="confirmed">Confirmed</option><option value="pending">Pending (hold)</option></Select></Field>
        <div className="sm:col-span-2 space-y-2"><div className="text-sm font-medium">Rooms</div>
          {!ok ? <p className="text-sm text-[var(--muted)]">Pick valid dates first.</p> : list.filter((c) => c.status === 'published' || c.status === undefined).map((c) => {
            const free = (avail.data ?? []).filter((r: any) => r.category_id === c.id)
            return <div key={c.id} className="flex flex-wrap items-center gap-2 text-sm"><span className="w-40 font-medium">{c.name}</span><span className="text-xs text-[var(--muted)]">{free.length} free</span>
              <Input className="w-20" type="number" min={0} max={free.length} value={sel[c.id] ?? 0} onChange={(e) => setSel({ ...sel, [c.id]: Number(e.target.value) })} aria-label={`Quantity ${c.name}`} />
              {(sel[c.id] ?? 0) === 1 && <Select className="w-36" value={rooms[c.id] ?? ''} onChange={(e) => setRooms({ ...rooms, [c.id]: e.target.value })} aria-label="Specific room"><option value="">Auto-assign</option>{free.map((r: any) => <option key={r.id} value={r.id}>Room {r.number}</option>)}</Select>}</div>
          })}</div></CardBody></Card>
      <Card><CardHeader><h3 className="font-semibold">Guest</h3></CardHeader><CardBody className="grid gap-3 sm:grid-cols-2">
        <Field label="Full name" className="sm:col-span-2"><Input {...s('name')} /></Field><Field label="Phone"><Input {...s('phone')} /></Field><Field label="Email (optional)"><Input type="email" {...s('email')} /></Field>
        <Field label="Country"><Input {...s('country')} /></Field><Field label="Promo code"><Input {...s('promo_code')} /></Field>
        <Field label="Guest requests" className="sm:col-span-2"><Textarea {...s('special_requests')} /></Field><Field label="Internal notes" className="sm:col-span-2"><Textarea {...s('internal_notes')} /></Field>
        <div className="sm:col-span-2"><Button loading={create.isPending} disabled={!ok || !picks.length || v.name.length < 2} onClick={() => create.mutate(undefined)}>Create reservation</Button></div></CardBody></Card></div></>)
}

export function ReservationDetail() {
  const { id = '' } = useParams()
  const { can } = useAuth()
  const q = useGet(['reservation', id], `/reservations/${id}`)
  const inv = [['reservation', id], ['reservations']] as any
  const [dlg, setDlg] = useState<string | null>(null)
  const [f, setF] = useState<any>({})
  const post = (path: string, body?: any) => api(`/reservations/${id}${path}`, { method: 'POST', body: body ?? {} })
  const confirm = useAct(() => post('/confirm'), { invalidate: inv, ok: 'Confirmed' })
  const noShow = useAct(() => post('/no-show'), { invalidate: inv, ok: 'Marked no-show' })
  const rejectC = useAct(() => post('/reject-cancellation'), { invalidate: inv, ok: 'Request rejected' })
  const reviewChange = useAct(() => post('/review-change-request'), { invalidate: inv, ok: 'Change request marked reviewed' })
  const cancel = useAct(() => post('/cancel', { reason: f.reason ?? '', waive_fee: !!f.waive, refund_amount_minor: f.refund !== undefined && f.refund !== '' ? toMinor(f.refund) : null }), { invalidate: inv, ok: 'Reservation cancelled', onOk: () => setDlg(null) })
  const dates = useAct(() => post('/modify-dates', { check_in: f.ci, check_out: f.co, reason: f.reason ?? '' }), { invalidate: inv, ok: 'Dates updated', onOk: () => setDlg(null) })
  const charge = useAct(() => post('/charges', { description: f.desc, amount_minor: toMinor(f.amt) }), { invalidate: inv, ok: 'Charge added', onOk: () => setDlg(null) })
  const pay = useAct(() => api('/payments/offline', { body: { reservation_id: id, amount_minor: toMinor(f.amt), method: f.method ?? 'cash', note: f.note ?? '', idempotency_key: f.idempotencyKey } }), { invalidate: inv, ok: 'Payment recorded', onOk: () => setDlg(null) })
  const refund = useAct(() => api('/refunds', { body: { reservation_id: id, amount_minor: toMinor(f.amt), reason: f.reason } }), { invalidate: inv, ok: 'Refund requested', onOk: () => setDlg(null) })
  const assign = useAct(() => post(`/rooms/${f.rr}/assign`, { room_id: f.room, reason: f.reason ?? '' }), { invalidate: inv, ok: 'Room assigned', onOk: () => setDlg(null) })
  const patch = useAct(() => api(`/reservations/${id}`, { method: 'PATCH', body: { internal_notes: f.notes } }), { invalidate: inv, ok: 'Notes saved' })
  const free = useGet(['freeRoomsFor', id, f.rr], '/availability/rooms', { check_in: q.data?.reservation.check_in, check_out: q.data?.reservation.check_out }, dlg === 'assign' && !!q.data)
  const open = (d: string, init: any = {}) => { setF(init); setDlg(d) }
  const r = q.data?.reservation
  return (<QueryState q={q}>{r && <>
    <PageHeader title={r.reference} desc={`${r.guest?.name} · ${fmtDate(r.check_in)} → ${fmtDate(r.check_out)} (${r.nights} nights)`} actions={<>
      <Button variant="outline" asChild><Link to={`/admin/reservations/${id}/print`} target="_blank"><Printer className="h-4 w-4" />Print</Link></Button>
      {can('reservations.manage') && r.status === 'pending' && <Button loading={confirm.isPending} onClick={() => confirm.mutate(undefined)}>Confirm</Button>}
      {can('reservations.manage') && ['pending', 'confirmed'].includes(r.status) && <Button variant="outline" onClick={() => open('dates', { ci: r.check_in, co: r.check_out })}>Change dates</Button>}
      {can('reservations.manage') && r.status === 'confirmed' && r.check_in < new Date().toISOString().slice(0, 10) && <Button variant="outline" onClick={() => noShow.mutate(undefined)}>No-show</Button>}
      {can('reservations.manage') && ['pending', 'confirmed', 'cancellation_requested'].includes(r.status) && <Button variant="destructive" onClick={() => open('cancel')}>Cancel</Button>}</>} />
    {r.needs_attention && <div className="mb-4 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">⚠ Needs attention: {r.attention_reason ?? 'payment received but rooms could not be secured. Review refund.'}</div>}
    {r.status === 'cancellation_requested' && <div className="mb-4 flex items-center justify-between rounded-lg border border-sky-300 bg-sky-50 p-3 text-sm text-sky-900"><span>Guest requested cancellation{r.cancellation_request?.reason ? `: ${r.cancellation_request.reason}` : ''}.</span>{can('reservations.manage') && <Button size="sm" variant="outline" onClick={() => rejectC.mutate(undefined)}>Reject request</Button>}</div>}
    {r.change_request && <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-sky-300 bg-sky-50 p-3 text-sm text-sky-900">
      <span>Guest change request ({r.change_request.status}): {r.change_request.message}</span>
      {can('reservations.manage') && r.change_request.status === 'pending' && <Button size="sm" variant="outline" loading={reviewChange.isPending} onClick={() => reviewChange.mutate(undefined)}>Mark reviewed</Button>}
    </div>}
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="space-y-4 lg:col-span-2">
        <Card><CardHeader><h3 className="font-semibold">Overview</h3><div className="flex gap-2"><StatusBadge status={r.status} /><StatusBadge status={r.payment_status} /></div></CardHeader><CardBody className="grid gap-3 text-sm sm:grid-cols-2">
          <div><div className="text-[var(--muted)]">Guest</div>{r.guest?.name}<br />{r.guest?.phone} {r.guest?.email}<br />{r.guest?.country}</div>
          <div><div className="text-[var(--muted)]">Guests / source</div>{r.adults} adults{r.children ? `, ${r.children} children` : ''} · {r.source}</div>
          <div className="sm:col-span-2"><div className="text-[var(--muted)]">Guest requests</div>{r.special_requests || '—'}</div>
          {r.hold_expires_at && r.status === 'pending' && <div className="sm:col-span-2 text-amber-700">Hold expires {fmtDateTime(r.hold_expires_at)}</div>}</CardBody></Card>
        <Card><CardHeader><h3 className="font-semibold">Rooms</h3></CardHeader><CardBody className="space-y-2 text-sm">{q.data.rooms.map((rr: any) => <div key={rr.id} className="flex flex-wrap items-center justify-between gap-2"><span>{rr.category_name} · <b>Room {rr.room_number}</b> <StatusBadge status={rr.status} /></span>
          {can('reservations.assign') && ['reserved', 'checked_in'].includes(rr.status) && <Button size="sm" variant="outline" onClick={() => open('assign', { rr: rr.id })}>Reassign</Button>}</div>)}</CardBody></Card>
        <Card><CardHeader><h3 className="font-semibold">Payments</h3>{can('payments.record') && r.balance > 0 && !['cancelled', 'expired'].includes(r.status) && <Button size="sm" onClick={() => open('pay', { amt: fromMinor(r.balance), method: 'cash', idempotencyKey: crypto.randomUUID() })}>Record payment</Button>}</CardHeader>
          <CardBody>{q.data.payments.length ? <Table><thead><tr><Th>Receipt</Th><Th>Method</Th><Th>Status</Th><Th>Amount</Th><Th>Date</Th></tr></thead><tbody>{q.data.payments.map((p: any) => <tr key={p.id}><Td>{p.receipt_number ?? '—'}</Td><Td>{p.method}</Td><Td><StatusBadge status={p.status} /></Td><Td>{money(p.amount)}</Td><Td>{fmtDateTime(p.created_at)}</Td></tr>)}</tbody></Table> : <p className="text-sm text-[var(--muted)]">No payments yet.</p>}</CardBody></Card>
        {q.data.refunds.length > 0 && <Card><CardHeader><h3 className="font-semibold">Refunds</h3></CardHeader><CardBody className="space-y-1 text-sm">{q.data.refunds.map((x: any) => <div key={x.id} className="flex justify-between"><span>{x.reason}</span><span className="flex gap-2">{money(x.amount)} <StatusBadge status={x.status} /></span></div>)}</CardBody></Card>}
      </div>
      <div className="space-y-4">
        <Card><CardHeader><h3 className="font-semibold">Charges & totals</h3>{can('reservations.manage') && <Button size="sm" variant="outline" onClick={() => open('charge')}>Add charge</Button>}</CardHeader><CardBody className="space-y-1 text-sm">
          <Line l="Accommodation" v={money(r.pricing?.accommodation_minor)} />{r.pricing?.extra_guest_minor > 0 && <Line l="Extra guests" v={money(r.pricing.extra_guest_minor)} />}
          {r.pricing?.discount?.amount_minor > 0 && <Line l={`Discount ${r.pricing.discount.code ?? ''}`} v={`− ${money(r.pricing.discount.amount_minor)}`} />}
          {r.pricing?.taxes?.map((t: any) => <Line key={t.name} l={t.name} v={money(t.amount_minor)} />)}{r.charges?.map((c: any, i: number) => <Line key={i} l={c.description} v={money(c.amount_minor)} />)}
          <div className="border-t border-[var(--border)] pt-2"><Line l="Total" v={money(r.total_amount)} bold /><Line l="Paid" v={money(r.amount_paid)} /><Line l="Balance" v={money(r.balance)} bold /></div>
          {can('refunds.manage') && r.amount_paid > 0 && <Button size="sm" variant="outline" className="mt-2 w-full" onClick={() => open('refund', { amt: '' })}>Request refund</Button>}</CardBody></Card>
        <Card><CardHeader><h3 className="font-semibold">Internal notes</h3></CardHeader><CardBody className="space-y-2"><Textarea defaultValue={r.internal_notes} onChange={(e) => setF({ ...f, notes: e.target.value })} disabled={!can('reservations.manage')} />{can('reservations.manage') && <Button size="sm" onClick={() => patch.mutate(undefined)} loading={patch.isPending}>Save notes</Button>}</CardBody></Card>
        {r.cancellation_preview && <Card><CardBody className="text-xs text-[var(--muted)]">If cancelled now: fee {money(r.cancellation_preview.fee_minor)}, refundable {money(r.cancellation_preview.refundable_minor)}.</CardBody></Card>}
        <Audit id={id} /></div></div>

    <Modal open={dlg === 'cancel'} onOpenChange={() => setDlg(null)} title="Cancel reservation" desc={r.cancellation_preview ? `Policy: fee ${money(r.cancellation_preview.fee_minor)}, refundable ${money(r.cancellation_preview.refundable_minor)}. Refunds are never automatic.` : undefined}>
      <div className="space-y-3"><Field label="Reason"><Textarea value={f.reason ?? ''} onChange={(e) => setF({ ...f, reason: e.target.value })} /></Field>
        {can('refunds.manage') && <><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!f.waive} onChange={(e) => setF({ ...f, waive: e.target.checked })} />Waive cancellation fee</label><Field label="Override refund amount (GHS, optional)"><Input type="number" step="0.01" value={f.refund ?? ''} onChange={(e) => setF({ ...f, refund: e.target.value })} /></Field></>}
        <Button variant="destructive" loading={cancel.isPending} onClick={() => cancel.mutate(undefined)}>Cancel reservation</Button></div></Modal>
    <Modal open={dlg === 'dates'} onOpenChange={() => setDlg(null)} title="Change dates" desc="Availability and price are re-checked; the price is re-quoted."><div className="space-y-3">
      <Field label="Check-in"><Input type="date" value={f.ci ?? ''} onChange={(e) => setF({ ...f, ci: e.target.value })} /></Field><Field label="Check-out"><Input type="date" value={f.co ?? ''} onChange={(e) => setF({ ...f, co: e.target.value })} /></Field>
      <Field label="Reason"><Input value={f.reason ?? ''} onChange={(e) => setF({ ...f, reason: e.target.value })} /></Field><Button loading={dates.isPending} onClick={() => dates.mutate(undefined)}>Update</Button></div></Modal>
    <Modal open={dlg === 'charge'} onOpenChange={() => setDlg(null)} title="Add charge"><div className="space-y-3"><Field label="Description"><Input value={f.desc ?? ''} onChange={(e) => setF({ ...f, desc: e.target.value })} /></Field><Field label="Amount (GHS)"><Input type="number" step="0.01" value={f.amt ?? ''} onChange={(e) => setF({ ...f, amt: e.target.value })} /></Field><Button loading={charge.isPending} onClick={() => charge.mutate(undefined)}>Add</Button></div></Modal>
    <Modal open={dlg === 'pay'} onOpenChange={() => setDlg(null)} title="Record offline payment"><div className="space-y-3"><Field label="Amount (GHS)"><Input type="number" step="0.01" value={f.amt ?? ''} onChange={(e) => setF({ ...f, amt: e.target.value })} /></Field>
      <Field label="Method"><Select value={f.method} onChange={(e) => setF({ ...f, method: e.target.value })}>{['cash', 'mobile_money', 'card_pos', 'bank_transfer', 'other'].map((m) => <option key={m} value={m}>{m.replace(/_/g, ' ')}</option>)}</Select></Field><Field label="Note"><Input value={f.note ?? ''} onChange={(e) => setF({ ...f, note: e.target.value })} /></Field><Button loading={pay.isPending} onClick={() => pay.mutate(undefined)}>Record</Button></div></Modal>
    <Modal open={dlg === 'refund'} onOpenChange={() => setDlg(null)} title="Request refund" desc="Needs approval, then processing. Never automatic."><div className="space-y-3"><Field label="Amount (GHS)"><Input type="number" step="0.01" value={f.amt ?? ''} onChange={(e) => setF({ ...f, amt: e.target.value })} /></Field><Field label="Reason (min 3 characters)"><Input value={f.reason ?? ''} onChange={(e) => setF({ ...f, reason: e.target.value })} /></Field><Button loading={refund.isPending} onClick={() => refund.mutate(undefined)}>Request</Button></div></Modal>
    <Modal open={dlg === 'assign'} onOpenChange={() => setDlg(null)} title="Reassign room"><div className="space-y-3"><Field label="Room"><Select value={f.room ?? ''} onChange={(e) => setF({ ...f, room: e.target.value })}><option value="">Select a free room</option>{(free.data ?? []).map((x: any) => <option key={x.id} value={x.id}>Room {x.number} — {x.category}</option>)}</Select></Field><Field label="Reason"><Input value={f.reason ?? ''} onChange={(e) => setF({ ...f, reason: e.target.value })} /></Field><Button loading={assign.isPending} disabled={!f.room} onClick={() => assign.mutate(undefined)}>Assign</Button></div></Modal>
  </>}</QueryState>)
}
const Line = ({ l, v, bold }: { l: string; v: string; bold?: boolean }) => <div className={`flex justify-between ${bold ? 'font-semibold' : ''}`}><span className="text-[var(--muted)]">{l}</span><span>{v}</span></div>
function Audit({ id }: { id: string }) {
  const q = useGet(['res-audit', id], `/reservations/${id}/audit`)
  const rows: any[] = Array.isArray(q.data) ? q.data : q.data?.items ?? []
  return <Card><CardHeader><h3 className="font-semibold">History</h3></CardHeader><CardBody className="max-h-64 space-y-2 overflow-auto text-xs">{rows.length ? rows.map((a) => <div key={a.id}><b>{a.action}</b> · {a.actor_name ?? 'system'}<div className="text-[var(--muted)]">{fmtDateTime(a.created_at)}</div></div>) : <p className="text-[var(--muted)]">No history.</p>}</CardBody></Card>
}

export function PrintReservation() {
  const { id = '' } = useParams()
  const q = useGet(['reservation', id], `/reservations/${id}`)
  const site = useGet(['hotel-profile'], '/hotel/profile')
  const r = q.data?.reservation; const p = site.data?.profile ?? site.data ?? {}
  if (!r) return <div className="p-8">Loading…</div>
  return (<div className="mx-auto max-w-2xl bg-white p-8 text-black"><div className="no-print mb-4 text-right"><Button onClick={() => window.print()}>Print</Button></div>
    <h1 className="text-2xl font-semibold">{p.name ?? 'New Leaders Hotel & Events Centre'}</h1><p className="text-sm">{p.address} {p.phone}</p><hr className="my-4" />
    <h2 className="text-xl">Booking confirmation — {r.reference}</h2>
    <table className="my-4 w-full text-sm"><tbody><tr><td>Guest</td><td>{r.guest?.name}</td></tr><tr><td>Check-in</td><td>{fmtDate(r.check_in)}</td></tr><tr><td>Check-out</td><td>{fmtDate(r.check_out)}</td></tr><tr><td>Rooms</td><td>{q.data.rooms.map((x: any) => `${x.category_name} (${x.room_number})`).join(', ')}</td></tr><tr><td>Total</td><td>{money(r.total_amount)}</td></tr><tr><td>Paid</td><td>{money(r.amount_paid)}</td></tr><tr><td>Balance</td><td>{money(r.balance)}</td></tr></tbody></table>
    {q.data.payments.filter((x: any) => x.status === 'success').map((x: any) => <p key={x.id} className="text-xs">Receipt {x.receipt_number}: {money(x.amount)} ({x.method})</p>)}</div>)
}
