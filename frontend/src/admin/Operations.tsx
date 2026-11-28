import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { useAct, useGet } from '@/lib/hooks'
import { Button } from '@/components/ui/button'
import { Check, Field, Input, Select, Textarea } from '@/components/ui/form'
import { Card, CardBody, CardHeader, Modal, PageHeader, QueryState, StatusBadge, Table, Td, Th } from '@/components/ui/ui'
import { fmtDate, money } from '@/lib/utils'

export function FrontDesk() {
  const { can } = useAuth(); const [date, setDate] = useState(new Date().toISOString().slice(0, 10)); const [dlg, setDlg] = useState<any>(null); const [f, setF] = useState<any>({})
  const arr = useGet(['arrivals'], '/check-in/arrivals', { date }); const dep = useGet(['departures'], '/check-out/departures', { date }); const inh = useGet(['inhouse'], '/check-in/in-house')
  const inv = [['arrivals'], ['departures'], ['inhouse'], ['dash']] as any; const mgr = can('reservations.manage')
  const ci = useAct(() => api(`/check-in/${dlg.r.id}`, { body: { id_verified: !!f.id, allow_early: !!f.early, override_payment: !!f.pay, override_room_status: !!f.room, note: f.note ?? '' } }), { ok: 'Checked in', invalidate: inv, onOk: () => setDlg(null) })
  const co = useAct(() => api(`/check-out/${dlg.r.id}`, { body: { allow_outstanding: !!f.out, reason: f.reason ?? '' } }), { ok: 'Checked out', invalidate: inv, onOk: () => setDlg(null) })
  const row = (r: any, kind: 'in' | 'out') => <tr key={r.id}><Td><Link className="underline" to={`/admin/reservations/${r.id}`}>{r.reference}</Link></Td><Td>{r.guest?.name}</Td><Td>{r.rooms_count}</Td><Td><StatusBadge status={r.status} /></Td><Td>{r.balance > 0 ? <span className="text-amber-700">{money(r.balance)}</span> : 'Settled'}</Td>
    <Td>{kind === 'in' && r.status !== 'checked_in' && <Button size="sm" onClick={() => { setF({}); setDlg({ kind, r }) }}>Check in</Button>}{kind === 'out' && r.status === 'checked_in' && <Button size="sm" onClick={() => { setF({}); setDlg({ kind, r }) }}>Check out</Button>}</Td></tr>
  const tbl = (q: any, kind: 'in' | 'out', empty: string) => <QueryState q={q} empty={{ show: q.data?.length === 0, text: empty } as any}><Table><thead><tr><Th>Reference</Th><Th>Guest</Th><Th>Rooms</Th><Th>Status</Th><Th>Balance</Th><Th /></tr></thead><tbody>{q.data?.map((r: any) => row(r, kind))}</tbody></Table></QueryState>
  return (<><PageHeader title="Check-in / check-out" actions={<Input type="date" aria-label="Date" value={date} onChange={(e) => setDate(e.target.value)} />} />
    <div className="grid gap-4 xl:grid-cols-2"><div><h2 className="mb-2 font-semibold">Arrivals</h2>{tbl(arr, 'in', 'No arrivals.')}</div><div><h2 className="mb-2 font-semibold">Departures</h2>{tbl(dep, 'out', 'No departures.')}</div></div>
    <h2 className="mb-2 mt-6 font-semibold">In house</h2><QueryState q={inh} empty={{ show: inh.data?.length === 0, text: 'No guests in house.' } as any}><Table><thead><tr><Th>Reference</Th><Th>Guest</Th><Th>Rooms</Th><Th>Check-out</Th><Th>Balance</Th></tr></thead><tbody>{inh.data?.map((r: any) => <tr key={r.id}><Td><Link className="underline" to={`/admin/reservations/${r.id}`}>{r.reference}</Link></Td><Td>{r.guest?.name}</Td><Td>{r.room_numbers.join(', ')}</Td><Td>{fmtDate(r.check_out)}</Td><Td>{money(r.balance)}</Td></tr>)}</tbody></Table></QueryState>
    <Modal open={!!dlg} onOpenChange={() => setDlg(null)} title={dlg?.kind === 'in' ? `Check in ${dlg?.r.reference}` : `Check out ${dlg?.r?.reference}`}>{dlg && <div className="space-y-3">
      {dlg.kind === 'in' ? <>
        <Check label="I have verified the guest's identity per hotel procedure" checked={!!f.id} onChange={(e) => setF({ ...f, id: e.target.checked })} />
        {dlg.r.balance > 0 && <p className="text-sm text-amber-700">Outstanding balance {money(dlg.r.balance)}.</p>}
        {mgr && <div className="space-y-1 rounded border border-dashed border-[var(--border)] p-2 text-sm"><div className="text-xs text-[var(--muted)]">Manager overrides</div><Check label="Allow early check-in" checked={!!f.early} onChange={(e) => setF({ ...f, early: e.target.checked })} /><Check label="Check in with unpaid balance" checked={!!f.pay} onChange={(e) => setF({ ...f, pay: e.target.checked })} /><Check label="Room not ready (override)" checked={!!f.room} onChange={(e) => setF({ ...f, room: e.target.checked })} /></div>}
        <Field label="Note"><Input value={f.note ?? ''} onChange={(e) => setF({ ...f, note: e.target.value })} /></Field><Button loading={ci.isPending} disabled={!f.id} onClick={() => ci.mutate(undefined)}>Check in</Button></>
        : <>{dlg.r.balance > 0 && <p className="text-sm text-amber-700">Outstanding balance {money(dlg.r.balance)}. Record payment on the reservation first.</p>}
          {mgr && dlg.r.balance > 0 && <><Check label="Check out with outstanding balance" checked={!!f.out} onChange={(e) => setF({ ...f, out: e.target.checked })} /><Field label="Reason"><Input value={f.reason ?? ''} onChange={(e) => setF({ ...f, reason: e.target.value })} /></Field></>}
          <Button loading={co.isPending} onClick={() => co.mutate(undefined)}>Check out</Button></>}</div>}</Modal></>)
}

const HK = ['dirty', 'cleaning', 'clean', 'inspection', 'ready', 'maintenance']
export function Housekeeping() {
  const { can } = useAuth(); const board = useGet(['hk'], '/housekeeping/board'); const tasks = useGet(['hktasks'], '/housekeeping/tasks')
  const set = useAct((v: { id: string; status: string }) => api(`/housekeeping/rooms/${v.id}`, { method: 'PATCH', body: { status: v.status } }), { invalidate: [['hk'], ['hktasks']], ok: 'Updated' })
  return (<><PageHeader title="Housekeeping" desc="Rooms become dirty after check-out and are not bookable-as-ready until marked ready." />
    <QueryState q={board} empty={{ show: board.data?.length === 0, text: 'No rooms.' } as any}><div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">{board.data?.map((r: any) => <Card key={r.id}><CardBody className="space-y-2 p-3"><div className="flex items-center justify-between"><b>Room {r.number}</b><StatusBadge status={r.display_status} /></div><div className="text-xs text-[var(--muted)]">Floor {r.floor || '—'} · {r.occupancy_status}</div>
      <Select aria-label={`Housekeeping status room ${r.number}`} disabled={!can('housekeeping.manage')} value={r.housekeeping_status} onChange={(e) => set.mutate({ id: r.id, status: e.target.value })}>{HK.map((s) => <option key={s} value={s}>{s}</option>)}</Select></CardBody></Card>)}</div></QueryState>
    <h2 className="mb-2 mt-6 font-semibold">Open tasks</h2><QueryState q={tasks} empty={{ show: tasks.data?.length === 0, text: 'No open tasks.' } as any}><Table><thead><tr><Th>Room</Th><Th>Type</Th><Th>Status</Th></tr></thead><tbody>{tasks.data?.map((t: any) => <tr key={t.id}><Td>{t.room_number}</Td><Td>{t.type}</Td><Td><StatusBadge status={t.status} /></Td></tr>)}</tbody></Table></QueryState></>)
}

export function Maintenance() {
  const [status, setStatus] = useState(''); const list = useGet(['maint'], '/maintenance', { status, page_size: 50 }); const rooms = useGet(['rooms'], '/rooms')
  const [m, setM] = useState<any>(null)
  const create = useAct(() => api('/maintenance', { body: { title: m.title, description: m.description ?? '', priority: m.priority ?? 'normal', room_ids: m.room_ids, block_rooms: m.block !== false, start_date: m.start || null, end_date: m.end || null } }), { ok: 'Request created', invalidate: [['maint'], ['calendar']], onOk: () => setM(null) })
  const upd = useAct((v: { id: string; status: string }) => api(`/maintenance/${v.id}`, { method: 'PATCH', body: { status: v.status } }), { ok: 'Updated', invalidate: [['maint'], ['calendar']] })
  return (<><PageHeader title="Maintenance" desc="Blocking rooms removes them from availability for the chosen dates." actions={<Button onClick={() => setM({ room_ids: [], priority: 'normal', block: true })}>New request</Button>} />
    <Select aria-label="Status" className="mb-4 w-44" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All</option>{['open', 'in_progress', 'done', 'cancelled'].map((s) => <option key={s}>{s}</option>)}</Select>
    <QueryState q={list} empty={{ show: list.data?.items.length === 0, text: 'No maintenance requests.' } as any}>{list.data && <Table><thead><tr><Th>Title</Th><Th>Rooms</Th><Th>Priority</Th><Th>Dates</Th><Th>Status</Th><Th /></tr></thead><tbody>{list.data.items.map((x: any) => <tr key={x.id}><Td>{x.title}</Td><Td>{(x.room_numbers ?? x.room_ids ?? []).join?.(', ')}</Td><Td>{x.priority}</Td><Td>{x.start_date ? `${fmtDate(x.start_date)} → ${fmtDate(x.end_date)}` : '—'}</Td><Td><StatusBadge status={x.status} /></Td>
      <Td><Select aria-label="Update status" value={x.status} onChange={(e) => upd.mutate({ id: x.id, status: e.target.value })}>{['open', 'in_progress', 'done', 'cancelled'].map((s) => <option key={s}>{s}</option>)}</Select></Td></tr>)}</tbody></Table>}</QueryState>
    <Modal open={!!m} onOpenChange={() => setM(null)} title="New maintenance request">{m && <div className="space-y-3">
      <Field label="Title"><Input value={m.title ?? ''} onChange={(e) => setM({ ...m, title: e.target.value })} /></Field><Field label="Description"><Textarea value={m.description ?? ''} onChange={(e) => setM({ ...m, description: e.target.value })} /></Field>
      <Field label="Rooms"><div className="flex max-h-32 flex-wrap gap-x-3 gap-y-1 overflow-auto">{(rooms.data ?? []).map((r: any) => <Check key={r.id} label={r.number} checked={m.room_ids.includes(r.id)} onChange={(e) => setM({ ...m, room_ids: e.target.checked ? [...m.room_ids, r.id] : m.room_ids.filter((i: string) => i !== r.id) })} />)}</div></Field>
      <div className="grid gap-3 sm:grid-cols-3"><Field label="Priority"><Select value={m.priority} onChange={(e) => setM({ ...m, priority: e.target.value })}>{['low', 'normal', 'high', 'urgent'].map((s) => <option key={s}>{s}</option>)}</Select></Field><Field label="Block from"><Input type="date" onChange={(e) => setM({ ...m, start: e.target.value })} /></Field><Field label="Block to"><Input type="date" onChange={(e) => setM({ ...m, end: e.target.value })} /></Field></div>
      <Check label="Block these rooms from booking" checked={m.block !== false} onChange={(e) => setM({ ...m, block: e.target.checked })} /><Button loading={create.isPending} disabled={!m.title || m.title.length < 3 || !m.room_ids.length} onClick={() => create.mutate(undefined)}>Create</Button></div>}</Modal></>)
}
