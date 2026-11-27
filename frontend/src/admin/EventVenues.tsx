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
import { fromMinor, money, toMinor } from '@/lib/utils'

const emptyVenue = {
  name: '', slug: '', description: '', capacity: 30, hourly_rate: '',
  opening_time: '06:00', closing_time: '23:00', capacity_confirmed: true, main_media_id: null as string | null,
  gallery_media_ids: [] as string[], status: 'draft',
}

function VenueForm({ venue, onClose }: { venue: any | null; onClose: () => void }) {
  const [v, setV] = useState<any>(venue ? {
    ...emptyVenue, ...venue, hourly_rate: fromMinor(venue.hourly_rate_minor),
    capacity_confirmed: venue.capacity_confirmed ?? venue.slug !== 'event-centre',
  } : emptyVenue)
  const save = useAct(() => {
    const body = {
      name: v.name, slug: v.slug || null, description: v.description, capacity: Number(v.capacity),
      hourly_rate_minor: toMinor(v.hourly_rate), opening_time: v.opening_time, closing_time: v.closing_time,
      capacity_confirmed: v.capacity_confirmed,
      main_media_id: v.main_media_id, gallery_media_ids: v.gallery_media_ids, status: v.status,
    }
    return venue ? api(`/event-venues/admin/${venue.id}`, { method: 'PATCH', body }) : api('/event-venues/admin', { body })
  }, { ok: 'Event venue saved', invalidate: [['event-venues-admin'], ['event-venues'], ['pub', 'event-venues']], onOk: onClose })
  const field = (key: string) => ({ value: v[key] ?? '', onChange: (e: any) => setV({ ...v, [key]: e.target.value }) })

  return (<div className="space-y-3">
    <div className="grid gap-3 sm:grid-cols-2">
      <Field label="Venue name"><Input required minLength={2} {...field('name')} /></Field>
      <Field label="URL slug (optional)"><Input {...field('slug')} placeholder="generated from name" /></Field>
      <Field label="Maximum capacity"><Input type="number" min={1} max={10000} required {...field('capacity')} /></Field>
      <Field label="Hourly rate (GHS)"><Input type="number" min={0} step="0.01" required {...field('hourly_rate')} /></Field>
      <Field label="Opens"><Input type="time" step={900} required {...field('opening_time')} /></Field>
      <Field label="Closes"><Input type="time" step={900} required {...field('closing_time')} /></Field>
    </div>
    {(v.slug === 'event-centre' || !v.capacity_confirmed) && <Check label="I confirmed this is the venue's actual maximum guest capacity." checked={v.capacity_confirmed} onChange={(e) => setV({ ...v, capacity_confirmed: e.target.checked })} />}
    <Field label="Description"><Textarea maxLength={3000} {...field('description')} /></Field>
    <MediaPicker label="Main image" category="event" value={v.main_media_id} onChange={(id: string | null) => setV({ ...v, main_media_id: id })} />
    <MediaPicker label="Gallery images" category="event" multiple value={v.gallery_media_ids} onChange={(ids: string[]) => setV({ ...v, gallery_media_ids: ids })} />
    <Field label="Status"><Select {...field('status')}><option value="draft">Draft</option><option value="published">Published / bookable</option></Select></Field>
    <p className="text-xs text-[var(--muted)]">Published venues with a non-zero hourly rate appear on the Events page. You can upload and select photos here; uploads are categorized as Event media. The event centre's starting capacity is only a 500+ placeholder; confirm its actual maximum before publishing.</p>
    <Button loading={save.isPending} disabled={v.name.trim().length < 2} onClick={() => save.mutate(undefined)}>Save venue</Button>
  </div>)
}

export function EventVenuesAdmin() {
  const { can } = useAuth()
  const manage = can('rooms.manage')
  const venues = useGet<any[]>(['event-venues-admin'], '/event-venues/admin')
  const [editor, setEditor] = useState<any>(false)
  const [archive, setArchive] = useState<any>(null)
  const defaults = useAct(() => api('/event-venues/admin/defaults', { body: {} }), {
    ok: 'Standard venues added', invalidate: [['event-venues-admin'], ['pub', 'event-venues']],
  })
  const archiveVenue = useAct(() => api(`/event-venues/admin/${archive.id}`, { method: 'DELETE' }), {
    ok: 'Venue archived', invalidate: [['event-venues-admin'], ['event-venues'], ['pub', 'event-venues']], onOk: () => setArchive(null),
  })

  return (<><PageHeader title="Event venues" desc="Set hourly rates, capacity, opening hours, photos and publishing status."
    actions={<><Button variant="outline" asChild><Link to="/events">View public events</Link></Button>{manage && <><Button variant="outline" loading={defaults.isPending} onClick={() => defaults.mutate(undefined)}>Add standard venues</Button><Button onClick={() => setEditor({})}><Plus className="h-4 w-4" />Add venue</Button></>}</>} />
    <Card className="mb-5"><CardBody className="text-sm text-[var(--muted)]">Use “Add standard venues” once to create the requested 100-seat and 30-seat conference rooms and the 500+ event centre. They start as drafts with no rate. Add photos and hourly rates; confirm the event centre's actual maximum guest capacity before publishing it.</CardBody></Card>
    <QueryState q={venues as any} empty={{ show: venues.data?.length === 0, text: 'No event venues yet. Add the standard venues or create one.' }}>
      {venues.data && <Table><thead><tr><Th>Venue</Th><Th>Capacity</Th><Th>Hourly rate</Th><Th>Hours</Th><Th>Status</Th><Th /></tr></thead>
        <tbody>{venues.data.map((v: any) => <tr key={v.id}><Td className="font-medium">{v.name}{v.id && v.main_image && <span className="ml-2 text-xs text-[var(--muted)]">Image set</span>}{v.capacity === 501 && <Badge tone="blue" className="ml-2">500+</Badge>}</Td>
          <Td>{!v.capacity_confirmed ? <><Badge tone="amber">{v.slug === 'event-centre' ? 'Confirm actual max' : 'Confirm capacity'}</Badge><div className="mt-1 text-xs">{v.capacity}</div></> : v.capacity === 501 && v.slug === 'event-centre' ? '500+' : v.capacity}</Td><Td>{v.hourly_rate_minor ? money(v.hourly_rate_minor) : <span className="text-amber-600">Not set</span>}</Td>
          <Td>{v.opening_time}–{v.closing_time}</Td><Td><StatusBadge status={v.status} /></Td>
          <Td>{manage && <><Button size="sm" variant="outline" onClick={() => setEditor(v)}>Edit</Button>{v.status !== 'archived' && <Button size="sm" variant="ghost" onClick={() => setArchive(v)}>Archive</Button>}</>}</Td>
        </tr>)}</tbody></Table>}
    </QueryState>
    <Modal wide open={editor !== false} onOpenChange={() => setEditor(false)} title={editor?.id ? 'Edit event venue' : 'New event venue'}>
      {editor !== false && <VenueForm venue={editor?.id ? editor : null} onClose={() => setEditor(false)} />}
    </Modal>
    <Confirm open={!!archive} onOpenChange={() => setArchive(null)} danger title={`Archive ${archive?.name}?`}
      desc="This venue will no longer accept new bookings. Existing bookings remain in the system."
      confirmLabel="Archive venue" loading={archiveVenue.isPending} onConfirm={() => archiveVenue.mutate(undefined)} />
  </>)
}

export function EventBookingsAdmin() {
  const bookings = useGet<any[]>(['event-bookings'], '/event-bookings/admin')
  const [cancel, setCancel] = useState<any>(null)
  const reject = useAct((id: string) => api(`/event-bookings/admin/${id}/reject-cancellation`, { method: 'POST' }), {
    ok: 'Cancellation request declined', invalidate: [['event-bookings']],
  })
  const cancelBooking = useAct(() => api(`/event-bookings/admin/${cancel.id}/cancel`, {
    method: 'POST', body: { reason: 'Cancelled by hotel staff' },
  }), { ok: 'Event booking cancelled', invalidate: [['event-bookings']] , onOk: () => setCancel(null) })

  return (<><PageHeader title="Event bookings" desc="Hourly event venue reservations and their payment status." />
    <QueryState q={bookings as any} empty={{ show: bookings.data?.length === 0, text: 'No event bookings have been made yet.' }}>
      {bookings.data && <Table><thead><tr><Th>Reference</Th><Th>Venue & event</Th><Th>Date / time</Th><Th>Guest</Th><Th>Guests</Th><Th>Total</Th><Th>Status</Th><Th>Payment</Th><Th /></tr></thead>
        <tbody>{bookings.data.map((b: any) => {
          const event = b.event_booking
          return <tr key={b.id}><Td className="font-medium">{b.reference}</Td>
            <Td>{event?.venue_name}<div className="text-xs text-[var(--muted)]">{event?.event_type}</div></Td>
            <Td>{event?.date}<div className="text-xs text-[var(--muted)]">{event?.start_time}–{event?.end_time}</div></Td>
            <Td>{b.guest?.name}<div className="text-xs text-[var(--muted)]">{b.guest?.email}</div></Td>
            <Td>{event?.attendees}</Td><Td>{money(b.total_amount, b.pricing?.currency)}</Td><Td><StatusBadge status={b.status} />{b.needs_attention && <div className="mt-1 text-xs text-red-700">{b.attention_reason}</div>}</Td>
            <Td><StatusBadge status={b.payment_status} /></Td><Td>{b.status === 'cancellation_requested' && <Button size="sm" variant="outline" loading={reject.isPending} onClick={() => reject.mutate(b.id)}>Decline request</Button>}{['pending', 'confirmed', 'cancellation_requested'].includes(b.status) && <Button size="sm" variant="destructive" onClick={() => setCancel(b)}>Cancel</Button>}</Td>
          </tr>
        })}</tbody></Table>}
    </QueryState>
    <Confirm open={!!cancel} onOpenChange={() => setCancel(null)} danger title={`Cancel booking ${cancel?.reference}?`}
      desc="This releases the event time. Any paid amount will be handled under the hotel cancellation and refund policy."
      confirmLabel="Cancel booking" loading={cancelBooking.isPending} onConfirm={() => cancelBooking.mutate(undefined)} />
  </>)
}
