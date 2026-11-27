import { useState, type ChangeEvent, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { AlertTriangle, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { api, errMsg } from '@/lib/api'
import { addDays, isoToday, money } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Check, Field, Input, Select, Textarea } from '@/components/ui/form'
import { Card, CardBody } from '@/components/ui/ui'
import { Img } from '@/components/Img'
import { Seo } from '@/components/Seo'
import { Container, PageHero } from './Parts'

const today = isoToday()

export function EventBooking() {
  const [params] = useSearchParams()
  const [form, setForm] = useState({
    venue_id: params.get('venue') ?? '', date: addDays(today, 1), start_time: '09:00', end_time: '10:00',
    attendees: 30, event_type: 'Engagement', name: '', email: '', phone: '', country: 'Ghana',
    special_requests: '', terms: false, payment_option: 'full',
  })
  const venues = useQuery({ queryKey: ['event-venues'], queryFn: () => api<any[]>('/event-venues', { auth: false }) })
  const venue = venues.data?.find((v) => v.id === form.venue_id)
  const quoteInput = {
    venue_id: form.venue_id, date: form.date, start_time: form.start_time, end_time: form.end_time,
    attendees: Number(form.attendees), event_type: form.event_type,
  }
  const canQuote = Boolean(form.venue_id && form.date && form.start_time && form.end_time && Number(form.attendees) > 0)
  const quote = useQuery({
    queryKey: ['event-quote', quoteInput], enabled: canQuote, retry: false,
    queryFn: () => api<any>('/event-bookings/quote', { auth: false, body: quoteInput }),
  })
  const booking = useMutation({
    mutationFn: () => api<any>('/event-bookings', { auth: false, body: {
      ...quoteInput, guest: { name: form.name, email: form.email, phone: form.phone, country: form.country },
      special_requests: form.special_requests, payment_option: form.payment_option,
    } }),
    onSuccess: (res) => {
      sessionStorage.setItem(`nlh_email_${res.reference}`, form.email)
      sessionStorage.setItem(`nlh_phone_${res.reference}`, form.phone)
      window.location.assign(res.authorization_url)
    },
    onError: (error) => toast.error(errMsg(error)),
  })
  const set = (key: string) => (e: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm((v) => ({ ...v, [key]: e.target.type === 'checkbox' ? (e.target as HTMLInputElement).checked : e.target.value }))
  const options = quote.data?.payment_options
  const valid = Boolean(quote.data?.available && quote.data?.total_minor > 0 && form.name.trim().length >= 2 &&
    form.email && form.phone.trim().length >= 7 && form.terms &&
    (form.payment_option === 'full' || options?.deposit))

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (valid) booking.mutate()
  }

  return (<><Seo title="Book an event venue" noindex /><PageHero title="Book an event venue" sub="Select a venue and time, then secure your booking with online payment." />
    <Container className="py-10">
      {venues.isError ? <Card><CardBody className="text-center text-red-700">{errMsg(venues.error)}</CardBody></Card> :
        venues.isLoading ? <Card><CardBody className="flex items-center justify-center gap-2"><Loader2 className="h-5 w-5 animate-spin" />Loading venues…</CardBody></Card> :
        !venues.data?.length ? <Card><CardBody className="space-y-3 text-center"><p>No event venues are available to book yet.</p><Button asChild variant="outline"><Link to="/events">Back to events</Link></Button></CardBody></Card> :
        <form onSubmit={submit} className="grid gap-8 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <Card><CardBody className="space-y-4">
              <h2 className="text-xl font-semibold text-forest-800">Event details</h2>
              <Field label="Venue"><Select required value={form.venue_id} onChange={set('venue_id')}><option value="">Choose a venue</option>{venues.data.map((v) => <option key={v.id} value={v.id}>{v.name} — up to {v.capacity}</option>)}</Select></Field>
              {venue && <div className="grid gap-4 sm:grid-cols-[160px_1fr]"><Img media={venue.main_image} className="aspect-[4/3] w-full rounded-lg" label={venue.name} /><div className="space-y-1"><h3 className="font-semibold">{venue.name}</h3><p className="text-sm text-[#4b5750]">{venue.description}</p><p className="text-sm">Capacity: {venue.capacity} · {money(venue.hourly_rate_minor)} / hour</p><p className="text-xs text-[#7a847e]">Booking hours: {venue.opening_time}–{venue.closing_time}</p></div></div>}
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Event date"><Input type="date" min={today} required value={form.date} onChange={set('date')} /></Field>
                <Field label="Expected guests"><Input type="number" min={1} max={venue?.capacity ?? 10000} required value={form.attendees} onChange={set('attendees')} /></Field>
                <Field label="Start time"><Input type="time" step={900} required value={form.start_time} onChange={set('start_time')} /></Field>
                <Field label="End time"><Input type="time" step={900} required value={form.end_time} onChange={set('end_time')} /></Field>
                <Field label="Event type"><Select value={form.event_type} onChange={set('event_type')}><option>Engagement</option><option>Wedding</option><option>Party</option><option>Conference</option><option>Other</option></Select></Field>
              </div>
              <Field label="Special requests (optional)"><Textarea maxLength={1000} value={form.special_requests} onChange={set('special_requests')} /></Field>
            </CardBody></Card>
            <Card><CardBody className="space-y-4">
              <h2 className="text-xl font-semibold text-forest-800">Your details</h2>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Full name"><Input required minLength={2} autoComplete="name" value={form.name} onChange={set('name')} /></Field>
                <Field label="Email (required for Paystack)" hint="Paystack requires an email for online payment."><Input required type="email" autoComplete="email" value={form.email} onChange={set('email')} /></Field>
                <Field label="Phone"><Input required minLength={7} autoComplete="tel" value={form.phone} onChange={set('phone')} /></Field>
                <Field label="Country"><Input required value={form.country} onChange={set('country')} /></Field>
              </div>
            </CardBody></Card>
          </div>
          <aside><Card className="sticky top-24"><CardBody className="space-y-4">
            <h2 className="text-xl font-semibold text-forest-800">Booking summary</h2>
            {quote.isError && <p role="alert" className="rounded bg-red-50 p-3 text-sm text-red-700">{errMsg(quote.error)}</p>}
            {quote.data && !quote.data.available && <p role="alert" className="rounded bg-amber-50 p-3 text-sm text-amber-800">That time is unavailable. Please choose another time.</p>}
            {quote.data?.available && <><div className="space-y-1 text-sm"><div className="flex justify-between gap-2"><span>Hourly rate</span><span>{money(quote.data.hourly_rate_minor)}</span></div>
              <div className="flex justify-between gap-2"><span>Duration</span><span>{quote.data.duration_minutes / 60} hour{quote.data.duration_minutes === 60 ? '' : 's'}</span></div>
              <div className="flex justify-between gap-2"><span>Venue hire</span><span>{money(quote.data.subtotal_minor, quote.data.currency)}</span></div>
              {quote.data.taxes.map((t: any) => <div key={t.name} className="flex justify-between gap-2"><span>{t.name}</span><span>{money(t.amount_minor, quote.data.currency)}</span></div>)}
              <div className="flex justify-between border-t border-sand pt-2 text-base font-semibold"><span>Total</span><span>{money(quote.data.total_minor, quote.data.currency)}</span></div></div>
              <div className="space-y-2">{options?.deposit && <label className="flex items-center justify-between gap-3 rounded border border-sand p-3 text-sm"><span><input type="radio" name="payment" value="deposit" checked={form.payment_option === 'deposit'} onChange={set('payment_option')} className="mr-2" />Pay deposit</span><b>{money(options.deposit, quote.data.currency)}</b></label>}
                <label className="flex items-center justify-between gap-3 rounded border border-sand p-3 text-sm"><span><input type="radio" name="payment" value="full" checked={form.payment_option === 'full'} onChange={set('payment_option')} className="mr-2" />Pay in full</span><b>{money(options.full, quote.data.currency)}</b></label></div>
            </>}
            {quote.isFetching && <p className="flex items-center gap-2 text-xs text-[#7a847e]"><Loader2 className="h-4 w-4 animate-spin" />Updating price and availability…</p>}
            <Check required checked={form.terms} onChange={set('terms')} label="I agree to the booking terms and cancellation policy." />
            <Button type="submit" variant="gold" size="lg" className="w-full" loading={booking.isPending} disabled={!valid || quote.isFetching}>Continue to secure payment</Button>
            <p className="text-xs text-[#7a847e]">Your selected time is held while you complete payment. Rates and availability are confirmed by the hotel system.</p>
          </CardBody></Card></aside>
        </form>}
    </Container></>)
}
