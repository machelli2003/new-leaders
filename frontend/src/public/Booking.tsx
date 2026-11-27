import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQuery } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle2, Loader2, Printer, XCircle } from 'lucide-react'
import { toast } from 'sonner'
import { api, errMsg } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Check, Field, Input, Select, Textarea } from '@/components/ui/form'
import { Card, CardBody, Skeleton, StatusBadge } from '@/components/ui/ui'
import { Img } from '@/components/Img'
import { Seo } from '@/components/Seo'
import { BookingBar, Container, PageHero } from './Parts'
import { useSite } from './data'
import { fmtDate, fmtDateTime, money } from '@/lib/utils'

type Sel = { category_id: string; name: string; quantity: number }
type Stay = { check_in: string; check_out: string; adults: number; children: number }
const KEY = 'nlh_booking'
const load = (): { stay: Stay; selections: Sel[] } | null => { try { return JSON.parse(sessionStorage.getItem(KEY) ?? 'null') } catch { return null } }

// ---------------- Search & select ----------------
export function BookingSearch() {
  const [sp] = useSearchParams()
  const nav = useNavigate()
  const stay: Stay = { check_in: sp.get('check_in') ?? '', check_out: sp.get('check_out') ?? '', adults: Number(sp.get('adults') ?? 2), children: Number(sp.get('children') ?? 0) }
  const wanted = Number(sp.get('rooms') ?? 1)
  const [qty, setQty] = useState<Record<string, number>>({})
  const ok = !!stay.check_in && !!stay.check_out
  const q = useQuery({
    queryKey: ['search', stay], enabled: ok, retry: false,
    queryFn: () => api<any[]>('/availability/search', { auth: false, body: { ...stay, selections: [{ category_id: 'x', quantity: 1 }] } }),
  })
  const total = Object.values(qty).reduce((a, b) => a + b, 0)
  const nights = q.data?.[0]?.nights ?? 0
  const picks = (q.data ?? []).filter((c) => qty[c.category_id] > 0)
  const go = () => {
    sessionStorage.setItem(KEY, JSON.stringify({ stay, selections: picks.map((c) => ({ category_id: c.category_id, name: c.name, quantity: qty[c.category_id] })) }))
    nav('/booking/checkout')
  }
  return (<><Seo title="Book your stay" noindex /><PageHero title="Book your stay" />
    <Container className="space-y-8 py-10">
      <div className="-mt-20 relative z-10"><BookingBar initial={sp.size ? Object.fromEntries(sp) : undefined} /></div>
      {!ok ? <p className="text-center text-[#5b665f]">Choose your dates to see available rooms.</p> : q.isLoading ? <div className="space-y-4"><Skeleton className="h-40" /><Skeleton className="h-40" /></div> :
        q.isError ? <Card><CardBody className="text-center text-red-700">{errMsg(q.error)}</CardBody></Card> :
        <div className="grid gap-8 lg:grid-cols-3">
          <div className="space-y-4 lg:col-span-2">
            <p className="text-sm text-[#5b665f]">{fmtDate(stay.check_in)} → {fmtDate(stay.check_out)} · {nights} night{nights === 1 ? '' : 's'} · {stay.adults} adult{stay.adults === 1 ? '' : 's'}{stay.children ? `, ${stay.children} child${stay.children === 1 ? '' : 'ren'}` : ''}</p>
            {!q.data?.length && <Card><CardBody className="text-center text-[#5b665f]">No rooms are published yet.</CardBody></Card>}
            {q.data?.map((c) => (
              <Card key={c.category_id} className={`overflow-hidden border-sand bg-white sm:flex ${c.available_rooms === 0 ? 'opacity-60' : ''}`}>
                <Img media={c.main_image} className="h-48 w-full sm:h-auto sm:w-64" sizes="256px" label={c.name} />
                <div className="flex flex-1 flex-col justify-between gap-4 p-5">
                  <div><h2 className="text-2xl font-semibold text-forest-800"><Link to={`/rooms/${c.slug}`} className="hover:underline">{c.name}</Link></h2><p className="mt-1 line-clamp-2 text-sm text-[#4b5750]">{c.short_description}</p>
                    <p className="mt-1 text-xs text-[#7a847e]">Up to {c.max_occupancy} guests{c.bed_configuration ? ` · ${c.bed_configuration}` : ''}</p></div>
                  <div className="flex flex-wrap items-end justify-between gap-3">
                    <div>{c.per_room_total_minor != null ? <><div className="text-xl font-semibold text-forest-800">{money(c.per_room_total_minor, c.currency)}</div><div className="text-xs text-[#7a847e]">per room for {c.nights} night{c.nights === 1 ? '' : 's'} (avg {money(c.avg_nightly_minor, c.currency)}/night, before taxes & fees)</div></> : <span className="text-sm text-[#7a847e]">Price unavailable</span>}</div>
                    {c.available_rooms === 0 ? <span className="rounded bg-stone-200 px-3 py-1.5 text-sm">Sold out</span> :
                      <div className="flex items-center gap-2"><span className="text-xs text-[#7a847e]">{c.available_rooms <= 3 ? `Only ${c.available_rooms} left` : ''}</span>
                        <Select aria-label={`Rooms of ${c.name}`} className="w-24" value={qty[c.category_id] ?? 0} onChange={(e) => setQty({ ...qty, [c.category_id]: Number(e.target.value) })}>{Array.from({ length: Math.min(c.available_rooms, 5) + 1 }, (_, i) => <option key={i} value={i}>{i === 0 ? 'Select' : `${i} room${i > 1 ? 's' : ''}`}</option>)}</Select></div>}
                  </div></div></Card>))}
          </div>
          <aside><Card className="sticky top-28 space-y-3 border-sand bg-white p-5"><h2 className="text-2xl font-semibold text-forest-800">Your selection</h2>
            {picks.length ? <ul className="space-y-1 text-sm">{picks.map((c) => <li key={c.category_id} className="flex justify-between"><span>{qty[c.category_id]} × {c.name}</span><span>{money(c.per_room_total_minor * qty[c.category_id], c.currency)}</span></li>)}</ul> : <p className="text-sm text-[#7a847e]">Select at least one room.</p>}
            {wanted > 1 && total !== wanted && total > 0 && <p className="rounded bg-amber-50 p-2 text-xs text-amber-800">You searched for {wanted} rooms but selected {total}.</p>}
            <p className="text-xs text-[#7a847e]">Taxes, fees and any promo code are calculated on the next step.</p>
            <Button variant="gold" size="lg" className="w-full" disabled={!total || total > 5} onClick={go}>Continue</Button></Card></aside>
        </div>}
    </Container></>)
}

// ---------------- Checkout ----------------
const schema = z.object({
  name: z.string().trim().min(2, 'Please enter your full name'),
  email: z.string().trim().email('Enter a valid email').or(z.literal('')),
  phone: z.string().trim().min(7, 'Enter a valid phone number').regex(/^[0-9+()\-\s]+$/, 'Digits only, e.g. +233 20 000 0000'),
  country: z.string().trim().min(2, 'Required'), special_requests: z.string().max(1000).optional(),
  payment: z.enum(['full', 'deposit', 'hotel']), terms: z.literal(true, { error: 'Please accept the terms to continue' }),
}).superRefine((values, ctx) => {
  if (values.payment !== 'hotel' && !values.email) {
    ctx.addIssue({ code: 'custom', path: ['email'], message: 'Email is required for online Paystack payments' })
  }
})
type FormVals = z.infer<typeof schema>

export function Checkout() {
  const nav = useNavigate()
  const saved = useMemo(load, [])
  const { data: site } = useSite()
  const [promoInput, setPromoInput] = useState('')
  const [promo, setPromo] = useState('')
  const body = saved ? { ...saved.stay, selections: saved.selections.map(({ category_id, quantity }) => ({ category_id, quantity })), promo_code: promo || undefined } : null
  const quote = useQuery({ queryKey: ['quote', body], enabled: !!body, retry: false, queryFn: () => api<any>('/bookings/quote', { auth: false, body }) })
  const { register, handleSubmit, formState: { errors }, watch } = useForm<FormVals>({ resolver: zodResolver(schema), defaultValues: { email: '', country: 'Ghana', payment: 'full' } as any })
  const q = quote.data
  const submit = useMutation({
    mutationFn: async (v: FormVals) => {
      const email = v.email.trim()
      const res = await api<any>('/bookings', { auth: false, body: { ...body, guest: { name: v.name, email: email || null, phone: v.phone, country: v.country }, special_requests: v.special_requests ?? '', pay_at_hotel: v.payment === 'hotel' } })
      if (email) sessionStorage.setItem(`nlh_email_${res.reference}`, email)
      else sessionStorage.removeItem(`nlh_email_${res.reference}`)
      sessionStorage.setItem(`nlh_phone_${res.reference}`, v.phone)
      if (v.payment === 'hotel') return { reference: res.reference, url: null as string | null }
      const pay = await api<any>('/bookings/pay', { auth: false, body: { reference: res.reference, email: v.email, option: v.payment } })
      return { reference: res.reference, url: pay.authorization_url as string }
    },
    onSuccess: (r) => { sessionStorage.removeItem(KEY); if (r.url) window.location.href = r.url; else nav(`/booking/${r.reference}`) },
    onError: (e) => toast.error(errMsg(e)),
  })
  useEffect(() => { if (!saved) nav('/booking/search', { replace: true }) }, [saved, nav])
  if (!saved) return null
  const pay = watch('payment')
  const amountNow = pay === 'full' ? q?.payment_options?.full : pay === 'deposit' ? q?.payment_options?.deposit : 0
  return (<><Seo title="Checkout" noindex /><PageHero title="Review & pay" />
    <Container className="py-10"><form onSubmit={handleSubmit((v) => submit.mutate(v))} className="grid gap-8 lg:grid-cols-5" noValidate>
      <div className="space-y-6 lg:col-span-3">
        <Card className="border-sand bg-white"><CardBody className="space-y-4"><h2 className="text-2xl font-semibold text-forest-800">Guest details</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Full name" error={errors.name?.message} className="sm:col-span-2"><Input autoComplete="name" {...register('name')} /></Field>
            <Field label={`Email${pay === 'hotel' ? ' (optional)' : ''}`} error={errors.email?.message} hint={pay === 'hotel' ? 'Optional. Add an email for email updates; booking lookup also works with your phone.' : 'Required by Paystack for online payment; email updates are sent here.'}><Input type="email" autoComplete="email" required={pay !== 'hotel'} {...register('email')} /></Field>
            <Field label="WhatsApp / telephone" error={errors.phone?.message}><Input type="tel" autoComplete="tel" {...register('phone')} /></Field>
            <Field label="Country" error={errors.country?.message}><Input autoComplete="country-name" {...register('country')} /></Field>
            <Field label="Special requests (optional)" className="sm:col-span-2"><Textarea {...register('special_requests')} placeholder="Late arrival, extra bed… (subject to availability)" /></Field></div></CardBody></Card>
        <Card className="border-sand bg-white"><CardBody className="space-y-3"><h2 className="text-2xl font-semibold text-forest-800">Payment</h2>
          {[['full', `Pay in full online${q ? ` (${money(q.payment_options.full, q.currency)})` : ''}`, true], ['deposit', `Pay a deposit online${q?.payment_options?.deposit ? ` (${money(q.payment_options.deposit, q.currency)})` : ''}; balance later`, !!q?.payment_options?.deposit], ['hotel', 'Pay at the hotel', !!site?.payment?.allow_pay_at_hotel]].filter((x) => x[2]).map(([v, label]) => (
            <label key={v as string} className="flex cursor-pointer items-center gap-3 rounded-lg border border-sand p-3 has-[:checked]:border-gold-500 has-[:checked]:bg-gold-300/10"><input type="radio" value={v as string} {...register('payment')} className="accent-[var(--color-forest-700)]" /><span className="text-sm">{label}</span></label>))}
          <p className="text-xs text-[#7a847e]">Online payments are processed securely by Paystack (cards and mobile money). Card details never touch our servers.</p></CardBody></Card>
        <div><Check label="I accept the Terms & Conditions and Cancellation Policy" {...register('terms')} /><p className="mt-1 text-xs text-[#7a847e]"><Link className="underline" to="/terms" target="_blank">Terms</Link> · <Link className="underline" to="/cancellation-policy" target="_blank">Cancellation policy</Link></p>{errors.terms && <p role="alert" className="mt-1 text-xs text-red-600">{errors.terms.message}</p>}</div>
      </div>
      <aside className="lg:col-span-2"><Card className="sticky top-28 space-y-3 border-sand bg-white p-5"><h2 className="text-2xl font-semibold text-forest-800">Summary</h2>
        {quote.isLoading && <Skeleton className="h-40" />}
        {quote.isError && <div className="rounded bg-red-50 p-3 text-sm text-red-700">{errMsg(quote.error)} <Link to="/booking/search" className="underline">Change search</Link></div>}
        {q && <>
          <p className="text-sm text-[#4b5750]">{fmtDate(q.check_in)} → {fmtDate(q.check_out)} · {q.nights} night{q.nights > 1 ? 's' : ''}</p>
          <ul className="space-y-1 text-sm">{saved.selections.map((s) => <li key={s.category_id}>{s.quantity} × {s.name}</li>)}</ul>
          <div className="space-y-1 border-t border-sand pt-3 text-sm">
            <Row l="Accommodation" v={money(q.accommodation_minor, q.currency)} />
            {q.extra_guest_minor > 0 && <Row l="Additional guests" v={money(q.extra_guest_minor, q.currency)} />}
            {q.discount?.amount_minor > 0 && <Row l={`Discount (${q.discount.code})`} v={`− ${money(q.discount.amount_minor, q.currency)}`} />}
            {q.taxes.map((t: any) => <Row key={t.name} l={t.name} v={money(t.amount_minor, q.currency)} />)}
            <div className="flex justify-between border-t border-sand pt-2 text-base font-semibold text-forest-800"><span>Total</span><span>{money(q.total_minor, q.currency)}</span></div></div>
          <div className="flex gap-2"><Input placeholder="Promo code" value={promoInput} onChange={(e) => setPromoInput(e.target.value)} aria-label="Promo code" /><Button type="button" variant="outline" onClick={() => setPromo(promoInput.trim())}>Apply</Button></div>
          <Button type="submit" variant="gold" size="lg" className="w-full" loading={submit.isPending}>{pay === 'hotel' ? 'Confirm booking' : `Pay ${money(amountNow ?? q.total_minor, q.currency)}`}</Button>
          <p className="text-xs text-[#7a847e]">{pay === 'hotel' ? 'Your room is reserved immediately.' : 'Your room is held while you complete payment.'}</p></>}
      </Card></aside>
    </form></Container></>)
}
const Row = ({ l, v }: { l: string; v: string }) => <div className="flex justify-between"><span className="text-[#5b665f]">{l}</span><span>{v}</span></div>

// ---------------- Lookup & manage ----------------
export function BookingLookup() {
  const nav = useNavigate()
  const [ref, setRef] = useState(''); const [contact, setContact] = useState('')
  return (<><Seo title="Find your booking" path="/booking/lookup" /><PageHero title="Find your booking" sub="Enter your booking reference and the email address or phone number used when booking." />
    <Container className="max-w-md py-12"><Card className="border-sand bg-white"><CardBody>
      <form className="space-y-4" onSubmit={(e) => {
        e.preventDefault()
        const reference = ref.trim().toUpperCase()
        const value = contact.trim()
        const isEmail = value.includes('@')
        sessionStorage.removeItem(`nlh_email_${reference}`)
        sessionStorage.removeItem(`nlh_phone_${reference}`)
        sessionStorage.setItem(`nlh_${isEmail ? 'email' : 'phone'}_${reference}`, value)
        nav(`/booking/${reference}`)
      }}>
        <Field label="Booking reference"><Input required value={ref} onChange={(e) => setRef(e.target.value)} placeholder="NLH-2026-000123" /></Field>
        <Field label="Email or WhatsApp number"><Input required value={contact} onChange={(e) => setContact(e.target.value)} /></Field>
        <Button variant="gold" className="w-full">Find booking</Button></form></CardBody></Card></Container></>)
}

export function BookingManage() {
  const { reference = '' } = useParams()
  const email = sessionStorage.getItem(`nlh_email_${reference}`) ?? ''
  const phone = sessionStorage.getItem(`nlh_phone_${reference}`) ?? ''
  const contact = email ? { email } : { phone }
  const { data: site } = useSite()
  const [cancelOpen, setCancelOpen] = useState(false); const [reason, setReason] = useState('')
  const q = useQuery({ queryKey: ['booking', reference, email, phone], enabled: !!(email || phone), retry: false, queryFn: () => api<any>('/bookings/lookup', { auth: false, body: { reference, ...contact } }) })
  const prev = useQuery({ queryKey: ['cprev', reference, email, phone], enabled: cancelOpen, queryFn: () => api<any>('/bookings/cancel-preview', { auth: false, body: { reference, ...contact } }) })
  const pay = useMutation({ mutationFn: (option: string) => api<any>('/bookings/pay', { auth: false, body: { reference, ...contact, option } }), onSuccess: (r) => { window.location.href = r.authorization_url }, onError: (e) => toast.error(errMsg(e)) })
  const cancel = useMutation({ mutationFn: () => api<any>('/bookings/cancel-request', { auth: false, body: { reference, ...contact, reason } }), onSuccess: () => { toast.success('Cancellation request sent'); setCancelOpen(false); q.refetch() }, onError: (e) => toast.error(errMsg(e)) })
  const b = q.data
  if (!email && !phone) return <BookingLookup />
  const whatsapp = b && whatsappBookingUrl(site?.profile?.socials?.whatsapp, bookingWhatsAppMessage(b, site?.profile?.name))
  return (<><Seo title="Your booking" noindex /><PageHero title="Your booking" sub={reference} />
    <Container className="max-w-3xl space-y-5 py-10">
      {q.isLoading && <Skeleton className="h-64" />}
      {q.isError && <Card><CardBody className="space-y-3 text-center"><p className="text-red-700">{errMsg(q.error)}</p><Button asChild variant="outline"><Link to="/booking/lookup">Try again</Link></Button></CardBody></Card>}
      {b && <>
        <Card className="border-sand bg-white"><CardBody className="space-y-4">
          <div className="flex flex-wrap items-center gap-2"><StatusBadge status={b.status} /><StatusBadge status={b.payment_status} /></div>
          {b.status === 'pending' && b.hold_expires_at && <p className="flex items-start gap-2 rounded bg-amber-50 p-3 text-sm text-amber-900"><AlertTriangle className="h-4 w-4 shrink-0" />Your {b.booking_type === 'event' ? 'event time' : 'room'} is held until {fmtDateTime(b.hold_expires_at)}. Complete payment to confirm it.</p>}
          {b.status === 'cancellation_requested' && <p className="rounded bg-sky-50 p-3 text-sm text-sky-900">Your cancellation request is being reviewed by the hotel.</p>}
          <dl className="grid gap-3 text-sm sm:grid-cols-2"><div><dt className="text-[#7a847e]">Guest</dt><dd>{b.guest.name}</dd></div>
            {b.booking_type === 'event' ? <>
              <div><dt className="text-[#7a847e]">Venue</dt><dd>{b.event_booking.venue_name}</dd></div>
              <div><dt className="text-[#7a847e]">Event date & time</dt><dd>{fmtDate(b.event_booking.date)} · {b.event_booking.start_time}–{b.event_booking.end_time}</dd></div>
              <div><dt className="text-[#7a847e]">Event / guests</dt><dd>{b.event_booking.event_type} · {b.event_booking.attendees}</dd></div>
            </> : <>
              <div><dt className="text-[#7a847e]">Stay</dt><dd>{fmtDate(b.check_in)} → {fmtDate(b.check_out)} ({b.nights} nights)</dd></div>
              <div><dt className="text-[#7a847e]">Guests</dt><dd>{b.adults} adults{b.children ? `, ${b.children} children` : ''}</dd></div>
              <div><dt className="text-[#7a847e]">Rooms</dt><dd>{b.rooms?.filter((r: any) => r.status !== 'cancelled').map((r: any) => r.category_name).join(', ')}</dd></div>
            </>}</dl>
          <div className="space-y-1 border-t border-sand pt-3 text-sm"><Row l="Total" v={money(b.total_amount, b.pricing.currency)} /><Row l="Paid" v={money(b.amount_paid, b.pricing.currency)} /><div className="flex justify-between font-semibold text-forest-800"><span>Balance</span><span>{money(b.balance, b.pricing.currency)}</span></div></div>
          {b.payments?.length > 0 && <div className="border-t border-sand pt-3 text-xs text-[#5b665f]"><div className="mb-1 font-medium">Payments</div>{b.payments.map((p: any) => <div key={p.reference} className="flex justify-between"><span>{p.receipt_number} · {p.method}</span><span>{money(p.amount, b.pricing.currency)}</span></div>)}</div>}
        </CardBody></Card>
        <div className="flex flex-wrap gap-3 no-print">
          {b.guest.email && b.payment_options?.deposit && <Button variant="gold" loading={pay.isPending} onClick={() => pay.mutate('deposit')}>Pay deposit {money(b.payment_options.deposit, b.pricing.currency)}</Button>}
          {b.guest.email && b.payment_options?.full > 0 && <Button variant={b.payment_options?.deposit ? 'outline' : 'gold'} loading={pay.isPending} onClick={() => pay.mutate('full')}>{b.amount_paid > 0 ? 'Pay balance' : 'Pay in full'} {money(b.payment_options.full, b.pricing.currency)}</Button>}
          {!b.guest.email && b.payment_options && <p className="w-full text-sm text-[#5b665f]">Online payment requires an email address for Paystack. Contact the hotel to add one to this booking.</p>}
          {whatsapp && <Button asChild variant="outline"><a href={whatsapp} target="_blank" rel="noreferrer noopener">Open WhatsApp to share booking details</a></Button>}
          <Button variant="outline" onClick={() => window.print()}><Printer className="h-4 w-4" />Print</Button>
          {['pending', 'confirmed'].includes(b.status) && <Button variant="ghost" className="text-red-700" onClick={() => setCancelOpen(true)}>Request cancellation</Button>}
        </div>
        {cancelOpen && <Card className="border-red-200 bg-white"><CardBody className="space-y-3"><h3 className="text-xl font-semibold">Request cancellation</h3>
          {prev.data && <p className="rounded bg-stone-50 p-3 text-sm">{prev.data.free_cancellation ? 'Free cancellation applies.' : `A cancellation fee of ${money(prev.data.fee_minor, b.pricing.currency)} may apply.`} {b.amount_paid > 0 && <>Based on current policy, up to {money(prev.data.refundable_minor, b.pricing.currency)} would be eligible for refund. Refunds are reviewed and approved by the hotel.</>}</p>}
          <Textarea placeholder="Reason (optional)" value={reason} onChange={(e) => setReason(e.target.value)} />
          <div className="flex gap-2"><Button variant="destructive" loading={cancel.isPending} onClick={() => cancel.mutate()}>Send request</Button><Button variant="outline" onClick={() => setCancelOpen(false)}>Keep booking</Button></div></CardBody></Card>}
      </>}</Container></>)
}

function bookingWhatsAppMessage(booking: any, hotelName?: string) {
  const details = booking.booking_type === 'event'
    ? `Event: ${booking.event_booking.venue_name}, ${fmtDate(booking.event_booking.date)} ${booking.event_booking.start_time}–${booking.event_booking.end_time} (${booking.event_booking.attendees} guests)`
    : `Stay: ${fmtDate(booking.check_in)} to ${fmtDate(booking.check_out)}`
  return [
    `Hello${hotelName ? ` ${hotelName}` : ''}, please confirm my booking details.`,
    `Reference: ${booking.reference}`,
    `Guest: ${booking.guest.name}`,
    details,
    `Status: ${booking.status}`,
  ].join('\n')
}

function whatsappBookingUrl(value: string | undefined, message: string): string | undefined {
  if (!value) return undefined
  let phone = value
  try {
    const url = new URL(value)
    if (url.hostname === 'wa.me') phone = url.pathname
    else if (url.hostname === 'api.whatsapp.com') phone = url.searchParams.get('phone') ?? ''
    else return undefined
  } catch {
    phone = value
  }
  const digits = phone.replace(/\D/g, '')
  return digits ? `https://wa.me/${digits}?text=${encodeURIComponent(message)}` : undefined
}

// ---------------- Payment result pages ----------------
export function PaymentSuccess() {
  const [sp] = useSearchParams()
  const nav = useNavigate()
  const ref = sp.get('reference') ?? sp.get('trxref') ?? ''
  const [tries, setTries] = useState(0)
  const q = useQuery({
    queryKey: ['paystatus', ref], enabled: !!ref, retry: false,
    queryFn: () => api<any>(`/bookings/payment-status/${ref}`, { auth: false }),
    refetchInterval: (query) => { const s = query.state.data?.status; return s === 'success' || s === 'failed' || s === 'flagged' || tries > 12 ? false : 3000 },
  })
  useEffect(() => { if (q.data) setTries((t) => t + 1) }, [q.dataUpdatedAt])
  useEffect(() => { if (q.data && ['failed', 'abandoned'].includes(q.data.status)) nav(`/booking/payment/failed?reference=${ref}`, { replace: true }) }, [q.data, nav, ref])
  const s = q.data
  return (<><Seo title="Payment" noindex /><PageHero title="Payment" />
    <Container className="max-w-lg py-12"><Card className="border-sand bg-white"><CardBody className="space-y-4 text-center">
      {!ref ? <><XCircle className="mx-auto h-12 w-12 text-red-500" /><p>No payment reference was provided.</p></> :
        s?.status === 'success' ? <><CheckCircle2 className="mx-auto h-14 w-14 text-emerald-600" /><h2 className="text-3xl font-semibold text-forest-800">Payment received</h2>
          {s.reservation_status === 'confirmed' ? <p className="text-[#4b5750]">Your booking <b>{s.reference}</b> is confirmed. View your booking for details and WhatsApp contact options.</p> : s.needs_attention ? <p className="text-amber-800">We received your payment but could not secure the {s.booking_type === 'event' ? 'event time' : 'room'}. The hotel will contact you about a refund. Reference <b>{s.reference}</b>.</p> : <p>Booking <b>{s.reference}</b> has been updated.</p>}
          <Button asChild variant="gold"><Link to={`/booking/${s.reference}`}>View booking</Link></Button></> :
        s?.status === 'flagged' ? <><AlertTriangle className="mx-auto h-12 w-12 text-amber-500" /><p>We could not automatically verify this payment. The hotel has been notified. Please contact us quoting <b>{s.reference}</b>.</p></> :
        <><Loader2 className="mx-auto h-12 w-12 animate-spin text-gold-500" /><h2 className="text-2xl font-semibold text-forest-800">Confirming your payment…</h2><p className="text-sm text-[#5b665f]">We verify every payment directly with Paystack. This usually takes a few seconds.</p>
          {tries > 12 && <p className="text-sm text-amber-800">This is taking longer than expected. Check your booking status again shortly, or look up your booking later.</p>}</>}
    </CardBody></Card></Container></>)
}

export function PaymentFailed() {
  const [sp] = useSearchParams()
  const ref = sp.get('reference') ?? ''
  const q = useQuery({ queryKey: ['pf', ref], enabled: !!ref, retry: false, queryFn: () => api<any>(`/bookings/payment-status/${ref}`, { auth: false }) })
  return (<><Seo title="Payment not completed" noindex /><PageHero title="Payment not completed" />
    <Container className="max-w-lg py-12"><Card className="border-sand bg-white"><CardBody className="space-y-4 text-center"><XCircle className="mx-auto h-14 w-14 text-red-500" />
      <p className="text-[#4b5750]">Your payment was not completed and you have not been charged for this attempt. {q.data?.reference ? <>Your {q.data.booking_type === 'event' ? 'event time' : 'room'} may still be held for a short time under <b>{q.data.reference}</b>.</> : null}</p>
      <div className="flex justify-center gap-3">{q.data?.reference && <Button asChild variant="gold"><Link to={`/booking/${q.data.reference}`}>Try payment again</Link></Button>}<Button asChild variant="outline"><Link to="/booking/search">New search</Link></Button></div></CardBody></Card></Container></>)
}
