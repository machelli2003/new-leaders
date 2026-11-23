import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus } from 'lucide-react'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { useAct, useGet } from '@/lib/hooks'
import { Button } from '@/components/ui/button'
import { Check, Field, Input, Select, Textarea } from '@/components/ui/form'
import { Badge, Card, CardBody, Confirm, Modal, PageHeader, QueryState, StatusBadge, Table, Td, Th } from '@/components/ui/ui'
import { MediaPicker } from '@/components/MediaPicker'
import { addDays, fromMinor, money, toMinor } from '@/lib/utils'

const emptyCat = { name: '', short_description: '', full_description: '', default_rate: '', max_occupancy: 2, included_guests: 2, extra_guest_fee: '', bed_configuration: '', room_size_sqm: '', amenity_ids: [] as string[], featured: false, status: 'draft', main_media_id: null as string | null, gallery_media_ids: [] as string[] }

function CategoryForm({ cat, onClose }: { cat: any | null; onClose: () => void }) {
  const [v, setV] = useState<any>(cat ? { ...emptyCat, ...cat, default_rate: fromMinor(cat.default_rate_minor), extra_guest_fee: fromMinor(cat.extra_guest_fee_minor), room_size_sqm: cat.room_size_sqm ?? '' } : emptyCat)
  const am = useGet(['amenities'], '/amenities')
  const body = () => ({ name: v.name, short_description: v.short_description, full_description: v.full_description, default_rate_minor: toMinor(v.default_rate), max_occupancy: Number(v.max_occupancy), included_guests: Number(v.included_guests) || null,
    extra_guest_fee_minor: toMinor(v.extra_guest_fee), bed_configuration: v.bed_configuration, room_size_sqm: v.room_size_sqm ? Number(v.room_size_sqm) : null, amenity_ids: v.amenity_ids, featured: v.featured, status: v.status, main_media_id: v.main_media_id, gallery_media_ids: v.gallery_media_ids })
  const save = useAct(() => cat ? api(`/room-categories/${cat.id}`, { method: 'PATCH', body: body() }) : api('/room-categories', { body: body() }), { ok: 'Saved', invalidate: [['cats'], ['rooms']], onOk: onClose })
  const [newAm, setNewAm] = useState('')
  const addAm = useAct(() => api('/amenities', { body: { name: newAm } }), { invalidate: [['amenities']], onOk: () => setNewAm('') })
  const s = (k: string) => ({ value: v[k] ?? '', onChange: (e: any) => setV({ ...v, [k]: e.target.value }) })
  return (<div className="space-y-3">
    <Field label="Category name"><Input {...s('name')} placeholder="e.g. Deluxe Room" /></Field>
    <Field label="Short description"><Input {...s('short_description')} /></Field><Field label="Full description"><Textarea {...s('full_description')} /></Field>
    <div className="grid grid-cols-2 gap-3"><Field label="Default nightly rate (GHS)"><Input type="number" step="0.01" min="0" {...s('default_rate')} /></Field><Field label="Max occupancy"><Input type="number" min={1} {...s('max_occupancy')} /></Field>
      <Field label="Guests included in rate"><Input type="number" min={1} {...s('included_guests')} /></Field><Field label="Extra guest fee / night (GHS)"><Input type="number" step="0.01" {...s('extra_guest_fee')} /></Field>
      <Field label="Bed configuration"><Input {...s('bed_configuration')} /></Field><Field label="Size (m²)"><Input type="number" {...s('room_size_sqm')} /></Field></div>
    <div><div className="mb-1 text-sm font-medium">Amenities</div><div className="flex flex-wrap gap-x-4 gap-y-1">{(am.data ?? []).map((a: any) => <Check key={a.id} label={a.name} checked={v.amenity_ids.includes(a.id)} onChange={(e) => setV({ ...v, amenity_ids: e.target.checked ? [...v.amenity_ids, a.id] : v.amenity_ids.filter((x: string) => x !== a.id) })} />)}</div>
      <div className="mt-2 flex gap-2"><Input placeholder="New amenity" value={newAm} onChange={(e) => setNewAm(e.target.value)} className="max-w-[200px]" /><Button type="button" size="sm" variant="outline" disabled={!newAm} onClick={() => addAm.mutate(undefined)}>Add</Button></div></div>
    <MediaPicker label="Main image" category="room" value={v.main_media_id} onChange={(x: string | null) => setV({ ...v, main_media_id: x })} />
    <MediaPicker label="Gallery" category="room" multiple value={v.gallery_media_ids} onChange={(x: string[]) => setV({ ...v, gallery_media_ids: x })} />
    <div className="flex items-center gap-4"><Field label="Status"><Select {...s('status')}><option value="draft">Draft</option><option value="published">Published</option><option value="archived">Archived</option></Select></Field><Check label="Featured on homepage" checked={v.featured} onChange={(e) => setV({ ...v, featured: e.target.checked })} /></div>
    <p className="text-xs text-[var(--muted)]">Only published categories with a rate appear on the website and can be booked online.</p>
    <Button loading={save.isPending} disabled={v.name.length < 2} onClick={() => save.mutate(undefined)}>Save category</Button></div>)
}

export function RoomsAdmin() {
  const { can } = useAuth(); const m = can('rooms.manage')
  const cats = useGet(['cats'], '/room-categories', { include_archived: true }); const rooms = useGet(['rooms'], '/rooms', { include_archived: true })
  const [catDlg, setCatDlg] = useState<any>(false); const [roomDlg, setRoomDlg] = useState<any>(false); const [bulk, setBulk] = useState(false); const [arch, setArch] = useState<any>(null)
  const [rf, setRf] = useState<any>({}); const [b, setB] = useState<any>({ prefix: '', start: 101, end: 110, floor: '' })
  const saveRoom = useAct(() => { const body = { number: rf.number, category_id: rf.category_id, floor: rf.floor ?? '', description: rf.description ?? '', operational_status: rf.operational_status ?? 'active', price_override_minor: rf.price ? toMinor(rf.price) : null, internal_notes: rf.internal_notes ?? '' }; return rf.id ? api(`/rooms/${rf.id}`, { method: 'PATCH', body }) : api('/rooms', { body }) }, { ok: 'Room saved', invalidate: [['rooms'], ['cats']], onOk: () => setRoomDlg(false) })
  const bulkM = useAct(() => api('/rooms/bulk', { body: { category_id: b.category_id, floor: b.floor, prefix: b.prefix, start: Number(b.start), end: Number(b.end) } }), { ok: 'Rooms created', invalidate: [['rooms'], ['cats']], onOk: () => setBulk(false) })
  const archive = useAct(() => api(`/rooms/${arch.id}`, { method: 'DELETE' }), { ok: 'Room archived', invalidate: [['rooms'], ['cats']], onOk: () => setArch(null) })
  const restore = useAct((id: string) => api(`/rooms/${id}/restore`, { method: 'POST' }), { ok: 'Restored', invalidate: [['rooms']] })
  const rl: any[] = rooms.data ?? []
  return (<><PageHeader title="Rooms & categories" desc="Categories are what guests book; physical rooms are what you assign." />
    <section className="mb-8"><div className="mb-2 flex items-center justify-between"><h2 className="text-lg font-semibold">Room categories</h2>{m && <Button size="sm" onClick={() => setCatDlg({})}><Plus className="h-4 w-4" />Add category</Button>}</div>
      <QueryState q={cats} empty={{ show: cats.data?.length === 0, text: 'No categories yet. Add the hotel’s real room types and rates.' } as any}>{cats.data && <Table><thead><tr><Th>Name</Th><Th>Rate / night</Th><Th>Occupancy</Th><Th>Rooms</Th><Th>Status</Th><Th /></tr></thead>
        <tbody>{cats.data.map((c: any) => <tr key={c.id}><Td className="font-medium">{c.name}{c.is_sample && <Badge tone="amber" className="ml-2">SAMPLE</Badge>}</Td><Td>{c.default_rate_minor ? money(c.default_rate_minor) : <span className="text-amber-600">Not set</span>}</Td><Td>{c.max_occupancy}</Td><Td>{c.room_count}</Td><Td><StatusBadge status={c.status} /></Td><Td>{m && <Button size="sm" variant="outline" onClick={() => setCatDlg(c)}>Edit</Button>}</Td></tr>)}</tbody></Table>}</QueryState></section>
    <section><div className="mb-2 flex items-center justify-between"><h2 className="text-lg font-semibold">Physical rooms</h2>{m && <div className="flex gap-2"><Button size="sm" variant="outline" disabled={!cats.data?.length} onClick={() => { setB({ ...b, category_id: cats.data?.[0]?.id }); setBulk(true) }}>Bulk create</Button><Button size="sm" disabled={!cats.data?.length} onClick={() => { setRf({ category_id: cats.data?.[0]?.id }); setRoomDlg(true) }}><Plus className="h-4 w-4" />Add room</Button></div>}</div>
      <QueryState q={rooms} empty={{ show: rl.length === 0, text: 'No rooms yet.' } as any}><Table><thead><tr><Th>Number</Th><Th>Category</Th><Th>Floor</Th><Th>Status</Th><Th>Override rate</Th><Th /></tr></thead>
        <tbody>{rl.map((r) => <tr key={r.id} className={r.archived ? 'opacity-50' : ''}><Td className="font-medium">{r.number}{r.is_sample && <Badge tone="amber" className="ml-2">SAMPLE</Badge>}</Td><Td>{r.category_name}</Td><Td>{r.floor}</Td><Td>{r.archived ? <Badge>Archived</Badge> : <StatusBadge status={r.display_status} />}</Td><Td>{r.price_override_minor ? money(r.price_override_minor) : '—'}</Td>
          <Td>{m && (r.archived ? <Button size="sm" variant="outline" onClick={() => restore.mutate(r.id)}>Restore</Button> : <><Button size="sm" variant="outline" onClick={() => { setRf({ ...r, price: fromMinor(r.price_override_minor) }); setRoomDlg(true) }}>Edit</Button> <Button size="sm" variant="ghost" onClick={() => setArch(r)}>Archive</Button></>)}</Td></tr>)}</tbody></Table></QueryState></section>
    <Modal wide open={catDlg !== false} onOpenChange={() => setCatDlg(false)} title={catDlg?.id ? 'Edit category' : 'New category'}>{catDlg !== false && <CategoryForm cat={catDlg?.id ? catDlg : null} onClose={() => setCatDlg(false)} />}</Modal>
    <Modal open={roomDlg} onOpenChange={setRoomDlg} title={rf.id ? 'Edit room' : 'Add room'}><div className="space-y-3">
      <Field label="Room number"><Input value={rf.number ?? ''} onChange={(e) => setRf({ ...rf, number: e.target.value })} /></Field>
      <Field label="Category"><Select value={rf.category_id ?? ''} onChange={(e) => setRf({ ...rf, category_id: e.target.value })}>{(cats.data ?? []).map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select></Field>
      <Field label="Floor"><Input value={rf.floor ?? ''} onChange={(e) => setRf({ ...rf, floor: e.target.value })} /></Field>
      <Field label="Operational status"><Select value={rf.operational_status ?? 'active'} onChange={(e) => setRf({ ...rf, operational_status: e.target.value })}><option value="active">Active</option><option value="out_of_service">Out of service</option><option value="maintenance">Maintenance</option></Select></Field>
      <Field label="Override nightly rate (GHS, optional)"><Input type="number" step="0.01" value={rf.price ?? ''} onChange={(e) => setRf({ ...rf, price: e.target.value })} /></Field>
      <Field label="Internal notes"><Textarea value={rf.internal_notes ?? ''} onChange={(e) => setRf({ ...rf, internal_notes: e.target.value })} /></Field>
      <Button loading={saveRoom.isPending} disabled={!rf.number} onClick={() => saveRoom.mutate(undefined)}>Save</Button></div></Modal>
    <Modal open={bulk} onOpenChange={setBulk} title="Bulk create rooms" desc="Creates one room per number in the range, e.g. prefix A, 1–10 → A1…A10."><div className="space-y-3">
      <Field label="Category"><Select value={b.category_id ?? ''} onChange={(e) => setB({ ...b, category_id: e.target.value })}>{(cats.data ?? []).map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select></Field>
      <div className="grid grid-cols-3 gap-3"><Field label="Prefix"><Input value={b.prefix} onChange={(e) => setB({ ...b, prefix: e.target.value })} /></Field><Field label="From"><Input type="number" value={b.start} onChange={(e) => setB({ ...b, start: e.target.value })} /></Field><Field label="To"><Input type="number" value={b.end} onChange={(e) => setB({ ...b, end: e.target.value })} /></Field></div>
      <Field label="Floor"><Input value={b.floor} onChange={(e) => setB({ ...b, floor: e.target.value })} /></Field><Button loading={bulkM.isPending} onClick={() => bulkM.mutate(undefined)}>Create</Button></div></Modal>
    <Confirm open={!!arch} onOpenChange={() => setArch(null)} title={`Archive room ${arch?.number}?`} desc="Rooms with future reservations cannot be archived. History is kept and the room can be restored." confirmLabel="Archive" danger loading={archive.isPending} onConfirm={() => archive.mutate(undefined)} /></>)
}

const CELL: Record<string, string> = { reserved: 'bg-sky-200 text-sky-900', hold: 'bg-amber-200 text-amber-900', occupied: 'bg-emerald-300 text-emerald-900', maintenance: 'bg-stone-400 text-white' }

export function CalendarPage() {
  const [start, setStart] = useState(new Date().toISOString().slice(0, 10)); const [days, setDays] = useState(14); const [cat, setCat] = useState('')
  const cats = useGet(['cats'], '/room-categories'); const q = useGet(['calendar'], '/availability/calendar', { start, days, category_id: cat })
  const d = q.data
  const cell = (rid: string, date: string) => d?.cells.find((c: any) => c.room_id === rid && c.date === date)
  return (<><PageHeader title="Availability calendar" actions={<div className="flex flex-wrap gap-2">
    <Button variant="outline" onClick={() => setStart(addDays(start, -days))}>←</Button><Input type="date" aria-label="Start date" value={start} onChange={(e) => setStart(e.target.value)} className="w-40" /><Button variant="outline" onClick={() => setStart(addDays(start, days))}>→</Button>
    <Select aria-label="Days" className="w-28" value={days} onChange={(e) => setDays(Number(e.target.value))}><option value={7}>7 days</option><option value={14}>14 days</option><option value={31}>31 days</option></Select>
    <Select aria-label="Category" className="w-40" value={cat} onChange={(e) => setCat(e.target.value)}><option value="">All categories</option>{(cats.data ?? []).map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select></div>} />
    <div className="mb-3 flex flex-wrap gap-3 text-xs">{[['reserved', 'Reserved'], ['hold', 'Held (unpaid)'], ['occupied', 'In house'], ['maintenance', 'Blocked']].map(([k, l]) => <span key={k} className="flex items-center gap-1"><i className={`h-3 w-3 rounded ${CELL[k]}`} />{l}</span>)}</div>
    <QueryState q={q} empty={{ show: d?.rooms.length === 0, text: 'No rooms to show.' } as any}>{d && <div className="overflow-auto rounded-xl border border-[var(--border)] bg-[var(--card)]"><table className="text-xs"><thead><tr><th className="sticky left-0 bg-[var(--card)] px-3 py-2 text-left">Room</th>{d.dates.map((x: string) => <th key={x} className="min-w-[56px] px-1 py-2 font-medium">{x.slice(8)}<div className="text-[10px] text-[var(--muted)]">{new Date(x + 'T00:00').toLocaleDateString('en-GB', { month: 'short' })}</div></th>)}</tr></thead>
      <tbody>{d.rooms.map((r: any) => <tr key={r.id} className="border-t border-[var(--border)]"><td className="sticky left-0 bg-[var(--card)] px-3 py-1.5 font-medium">{r.number}<div className="text-[10px] font-normal text-[var(--muted)]">{r.category}</div></td>
        {d.dates.map((x: string) => { const c = cell(r.id, x); return <td key={x} className="p-0.5">{c ? (c.reservation_id ? <Link title={`${c.guest ?? ''} ${c.reference ?? ''}`} to={`/admin/reservations/${c.reservation_id}`} className={`block truncate rounded px-1 py-1.5 ${CELL[c.kind]}`}>{c.guest?.split(' ')[0] ?? c.reference}</Link> : <div title={c.label} className={`truncate rounded px-1 py-1.5 ${CELL.maintenance}`}>{c.label}</div>) : <div className="h-7 rounded bg-[var(--soft)]" />}</td> })}</tr>)}</tbody></table></div>}</QueryState></>)
}
