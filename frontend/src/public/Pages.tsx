import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ChevronDown, Clock, MapPin, Phone, Mail, X } from 'lucide-react'
import { Img } from '@/components/Img'
import { GallerySlideshow } from '@/components/Slideshow'
import { Seo } from '@/components/Seo'
import { Button } from '@/components/ui/button'
import { Container, Heading, PageHero, Pending, Prose, RoomCard, Section } from './Parts'
import { useGallery, useItems, useOffers, useRoom, useRooms, useSection, useSite } from './data'
import { QueryState } from '@/components/ui/ui'
import { money } from '@/lib/utils'
import { Check, Users, BedDouble, Ruler } from 'lucide-react'

export function About() {
  const c = useSection('about').data?.content
  return (<><Seo title="About" path="/about" /><PageHero title={c?.title ?? 'About the hotel'} />
    <Section><div className="grid gap-12 lg:grid-cols-2">{c?.body ? <Prose text={c.body} /> : <Pending what="The hotel story" />}<Img media={c?.image} className="aspect-[4/3] w-full rounded-2xl" label="About" /></div>
      {!!c?.highlights?.length && <div className="mt-14 grid gap-6 md:grid-cols-3">{c.highlights.map((h: any, i: number) => <div key={i} className="rounded-xl border border-sand bg-white p-6"><h3 className="text-2xl font-semibold text-forest-800">{h.title}</h3><p className="mt-2 text-sm text-[#4b5750]">{h.text}</p></div>)}</div>}</Section></>)
}

export function Rooms() {
  const q = useRooms()
  return (<><Seo title="Rooms & Suites" path="/rooms" /><PageHero title="Rooms & Suites" sub="Comfortable accommodation for every stay." />
    <Section><QueryState q={q as any} empty={{ show: !q.data?.length, text: 'Rooms will appear here once published by the hotel.' }}>
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">{q.data?.map((r) => <RoomCard key={r.id} room={r} />)}</div></QueryState></Section></>)
}

export function RoomDetail() {
  const { slug = '' } = useParams()
  const q = useRoom(slug)
  const r = q.data
  const [active, setActive] = useState(0)
  const imgs = r ? [r.main_image, ...(r.gallery_images ?? [])].filter(Boolean) : []
  return (<><Seo title={r?.name} description={r?.short_description} path={`/rooms/${slug}`} />
    <Section><QueryState q={q as any}>{r && <div className="grid gap-10 lg:grid-cols-5">
      <div className="lg:col-span-3"><Img media={imgs[active]} eager className="aspect-[4/3] w-full rounded-2xl" label={r.name} />
        {imgs.length > 1 && <div className="mt-3 grid grid-cols-5 gap-2">{imgs.map((m: any, i: number) => <button key={m.id} onClick={() => setActive(i)} aria-label={`Photo ${i + 1}`} className={`overflow-hidden rounded-lg border-2 ${i === active ? 'border-gold-500' : 'border-transparent'}`}><Img media={m} className="aspect-square w-full" sizes="120px" /></button>)}</div>}</div>
      <div className="space-y-5 lg:col-span-2">
        <h1 className="text-5xl font-semibold text-forest-800">{r.name}</h1>
        {r.is_sample && <p className="rounded bg-amber-100 px-3 py-1.5 text-xs text-amber-900">Sample data: not confirmed hotel information.</p>}
        <p className="text-[#38443d]">{r.short_description}</p>
        <div className="flex flex-wrap gap-4 text-sm text-[#4b5750]"><span className="flex items-center gap-1.5"><Users className="h-4 w-4" />Up to {r.max_occupancy} guests</span>
          {r.bed_configuration && <span className="flex items-center gap-1.5"><BedDouble className="h-4 w-4" />{r.bed_configuration}</span>}{r.room_size_sqm && <span className="flex items-center gap-1.5"><Ruler className="h-4 w-4" />{r.room_size_sqm} m²</span>}</div>
        <div className="rounded-xl border border-sand bg-white p-5">{r.default_rate_minor ? <><div className="text-xs uppercase text-[#7a847e]">Starting from</div><div className="text-3xl font-semibold text-forest-800">{money(r.default_rate_minor)}<span className="text-sm font-normal text-[#7a847e]"> / night</span></div><p className="mt-1 text-xs text-[#7a847e]">Final price depends on your dates; seasonal rates and taxes are calculated at booking.</p></> : <p className="text-sm text-[#5b665f]">Please enquire for the rate.</p>}
          <Button asChild variant="gold" size="lg" className="mt-4 w-full"><Link to="/booking/search">Check availability & book</Link></Button></div>
        {r.full_description && <Prose text={r.full_description} />}
        {r.amenities?.length > 0 && <div><h2 className="mb-3 text-2xl font-semibold text-forest-800">Amenities</h2><ul className="grid grid-cols-2 gap-2 text-sm">{r.amenities.map((a: any) => <li key={a.id} className="flex items-center gap-2"><Check className="h-4 w-4 text-gold-500" />{a.name}</li>)}</ul></div>}
      </div></div>}</QueryState></Section></>)
}

export function Facilities() {
  const q = useItems('facility')
  return (<><Seo title="Facilities" path="/facilities" /><PageHero title="Facilities & Amenities" sub="Everything you need for a comfortable stay." />
    <Section><QueryState q={q as any} empty={{ show: !q.data?.length, text: 'Facilities will appear here once published.' }}>
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">{q.data?.map((f) => <article key={f.id} className="overflow-hidden rounded-xl border border-sand bg-white"><Img media={f.image} className="aspect-[16/10] w-full" label={f.title} /><div className="p-5"><h3 className="text-2xl font-semibold text-forest-800">{f.title}</h3><p className="mt-2 text-sm text-[#4b5750]">{f.body}</p></div></article>)}</div></QueryState></Section></>)
}

export function Restaurant() {
  const c = useSection('restaurant').data?.content
  const hasDetails = Boolean(c?.opening_hours || c?.menu_highlights?.length)
  return (<><Seo title="Restaurant & Dining" path="/restaurant" /><PageHero title={c?.title ?? 'Restaurant & Dining'} sub={c?.intro} />
    <Section>{!c ? <Pending what="Dining information" /> : <div className={hasDetails ? 'grid gap-12 lg:grid-cols-2' : ''}>{hasDetails && <div>
      {c.opening_hours && <p className="mb-6 flex items-start gap-2 text-[#38443d]"><Clock className="mt-0.5 h-5 w-5 text-gold-500" /><span className="whitespace-pre-line">{c.opening_hours}</span></p>}
      {!!c.menu_highlights?.length && <><h2 className="mb-4 text-3xl font-semibold text-forest-800">Menu highlights</h2><ul className="divide-y divide-sand">{c.menu_highlights.map((m: any, i: number) => <li key={i} className="flex justify-between gap-4 py-3"><div><div className="font-medium">{m.name}</div><div className="text-sm text-[#5b665f]">{m.description}</div></div>{m.price_minor ? <div className="font-semibold text-forest-800">{money(m.price_minor)}</div> : null}</li>)}</ul></>}</div>}
      <div className={`grid gap-4 sm:grid-cols-2 self-start ${hasDetails ? '' : 'lg:grid-cols-3'}`}>{(c.images?.length ? c.images : [null]).slice(0, 3).map((m: any, i: number) => <Img key={i} media={m} className="aspect-[16/10] w-full rounded-xl" label="Restaurant" />)}</div></div>}</Section></>)
}

export function Events() {
  const c = useSection('events').data?.content
  const items = useItems('event').data
  const site = useSite().data
  const hasDetails = Boolean(c?.capacity_text || c?.services?.length || c?.enquiry_text || items?.length)
  return (<><Seo title="Events & Conferences" path="/events" /><PageHero title={c?.title ?? 'Events & Conferences'} sub={c?.intro} />
    <Section>{!c && !items?.length ? <Pending what="Event information" /> : <div className={hasDetails ? 'grid gap-12 lg:grid-cols-2' : ''}>{hasDetails && <div className="space-y-8">
      {c?.capacity_text && <Prose text={c.capacity_text} />}
      {!!c?.services?.length && <div className="grid gap-4 sm:grid-cols-2">{c.services.map((s: any, i: number) => <div key={i} className="rounded-xl border border-sand bg-white p-5"><h3 className="text-xl font-semibold text-forest-800">{s.title}</h3><p className="mt-1 text-sm text-[#4b5750]">{s.text}</p></div>)}</div>}
      {c?.enquiry_text && <div className="rounded-xl bg-forest-800 p-6 text-white"><h3 className="text-2xl font-semibold">Enquire about your event</h3><p className="mt-2 whitespace-pre-line text-white/85">{c.enquiry_text}</p>{site?.profile?.phones?.[0] && <Button asChild variant="gold" className="mt-4"><a href={`tel:${site.profile.phones[0]}`}>Call {site.profile.phones[0]}</a></Button>}</div>}
      {items?.map((e) => <article key={e.id} className="rounded-xl border border-sand bg-white p-5"><h3 className="text-xl font-semibold">{e.title}</h3><p className="mt-1 text-sm text-[#4b5750]">{e.body}</p></article>)}</div>}
      <div className={`grid gap-4 sm:grid-cols-2 self-start ${hasDetails ? '' : 'lg:grid-cols-3'}`}>{(c?.images?.length ? c.images : [null]).slice(0, 3).map((m: any, i: number) => <Img key={i} media={m} className="aspect-[16/10] w-full rounded-xl" label="Events" />)}</div></div>}</Section></>)
}

export function Gallery() {
  const q = useGallery()
  const [open, setOpen] = useState<any>(null)
  return (<><Seo title="Gallery" path="/gallery" /><PageHero title="Gallery" sub="Explore New Leaders Hotel & Events Centre." />
    <Section><QueryState q={q as any} empty={{ show: !q.data?.length, text: 'Photographs will appear here once uploaded to the gallery.' }}>
      {!!q.data?.length && <GallerySlideshow images={q.data} onOpen={setOpen} />}
    </QueryState>
      {open && <div className="animate-fade-in fixed inset-0 z-50 grid place-items-center bg-black/90 p-4" role="dialog" aria-modal="true" onClick={() => setOpen(null)}><button className="absolute right-4 top-4 text-white" aria-label="Close"><X /></button><img src={open.variants?.lg ?? open.url} alt={open.alt} className="max-h-[90vh] max-w-full rounded" /></div>}</Section></>)
}

export function Offers() {
  const q = useOffers()
  return (<><Seo title="Special Offers" path="/offers" /><PageHero title="Special Offers" />
    <Section><QueryState q={q as any} empty={{ show: !q.data?.length, text: 'There are no special offers at the moment. Please check back soon.' }}>
      <div className="grid gap-6 md:grid-cols-2">{q.data?.map((o) => <article key={o.id} className="overflow-hidden rounded-2xl border border-sand bg-white"><Img media={o.image} className="aspect-[16/8] w-full" label="Offer" /><div className="space-y-2 p-6"><h2 className="text-3xl font-semibold text-forest-800">{o.title}</h2><p className="text-[#4b5750]">{o.description}</p>
        {o.code && !o.hide_code && <p className="text-sm">Promo code: <b className="rounded bg-gold-300/30 px-2 py-0.5">{o.code}</b></p>}{o.valid_to && <p className="text-xs text-[#7a847e]">Valid until {o.valid_to}</p>}
        <Button asChild variant="gold" className="mt-2"><Link to="/booking/search">Book now</Link></Button></div></article>)}</div></QueryState></Section></>)
}

export function Contact() {
  const { data: site } = useSite()
  const c = useSection('contact').data?.content
  const p = site?.profile
  const src = typeof c?.map_embed_url === 'string' && /^https:\/\/(www\.)?google\.[a-z.]+\/maps\/embed/.test(c.map_embed_url) ? c.map_embed_url : null
  return (<><Seo title="Contact" path="/contact" /><PageHero title="Contact us" sub={c?.intro} />
    <Section><div className="grid gap-10 lg:grid-cols-2"><div className="space-y-6">
      <ul className="space-y-4 text-[#38443d]">
        {(p?.address || p?.town) && <li className="flex gap-3"><MapPin className="h-5 w-5 text-gold-500" /><span>{[p.address, p.town, p.region, p.country].filter(Boolean).join(', ')}</span></li>}
        {p?.phones?.map((x: string) => <li key={x} className="flex gap-3"><Phone className="h-5 w-5 text-gold-500" /><a href={`tel:${x}`} className="hover:underline">{x}</a></li>)}
        {p?.emails?.map((x: string) => <li key={x} className="flex gap-3"><Mail className="h-5 w-5 text-gold-500" /><a href={`mailto:${x}`} className="hover:underline">{x}</a></li>)}
        {c?.opening_hours && <li className="flex gap-3"><Clock className="h-5 w-5 text-gold-500" />{c.opening_hours}</li>}
      </ul>
      {!p?.phones?.length && !p?.emails?.length && <Pending what="Contact details" />}
      {c?.directions && <Prose text={c.directions} />}</div>
      <div>{src ? <iframe title="Map" src={src} className="h-96 w-full rounded-2xl border-0" loading="lazy" referrerPolicy="no-referrer-when-downgrade" /> : <div className="grid h-96 place-items-center rounded-2xl bg-sand text-sm text-[#7a847e]">Map will appear once the hotel adds it.</div>}</div></div></Section></>)
}

export function FAQ() {
  const q = useItems('faq')
  const [open, setOpen] = useState<string | null>(null)
  return (<><Seo title="FAQs" path="/faq" /><PageHero title="Frequently asked questions" />
    <Section><Container className="max-w-3xl"><QueryState q={q as any} empty={{ show: !q.data?.length, text: 'FAQs will appear here once published.' }}>
      <div className="divide-y divide-sand rounded-xl border border-sand bg-white">{q.data?.map((f) => <div key={f.id}><button className="flex w-full items-center justify-between gap-4 p-5 text-left font-medium text-forest-800" aria-expanded={open === f.id} onClick={() => setOpen(open === f.id ? null : f.id)}>{f.question}<ChevronDown className={`h-5 w-5 shrink-0 transition-transform ${open === f.id ? 'rotate-180' : ''}`} /></button>{open === f.id && <div className="px-5 pb-5 text-sm leading-relaxed text-[#4b5750]">{f.answer}</div>}</div>)}</div></QueryState></Container></Section></>)
}

export function Policy({ kind }: { kind: 'privacy' | 'terms' | 'cancellation' }) {
  const c = useSection(`policy.${kind}`).data?.content
  const site = useSite().data
  const titles = { privacy: 'Privacy Policy', terms: 'Terms & Conditions', cancellation: 'Cancellation Policy' }
  const path = { privacy: '/privacy-policy', terms: '/terms', cancellation: '/cancellation-policy' }[kind]
  const pol = site?.cancellation
  return (<><Seo title={titles[kind]} path={path} /><PageHero title={c?.title ?? titles[kind]} />
    <Section><Container className="max-w-3xl space-y-8">
      {kind === 'cancellation' && pol && <div className="rounded-xl border border-sand bg-white p-5 text-sm"><h2 className="mb-2 text-2xl font-semibold text-forest-800">How cancellation works</h2><ul className="list-disc space-y-1 pl-5 text-[#38443d]">
        {pol.non_refundable ? <li>Bookings are non-refundable.</li> : <><li>Free cancellation up to {pol.free_cancellation_hours} hours before check-in.</li><li>After that, a fee of {pol.late_fee_percent}% of the booking total applies.</li></>}</ul>{pol.description && <p className="mt-3 text-[#4b5750]">{pol.description}</p>}</div>}
      {c?.body ? <Prose text={c.body} /> : kind !== 'cancellation' ? <Pending what={titles[kind]} /> : null}</Container></Section></>)
}
