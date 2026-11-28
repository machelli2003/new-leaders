import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ChevronDown, Clock, MapPin, Phone, Mail, Users, X } from 'lucide-react'
import { Img } from '@/components/Img'
import { GallerySlideshow } from '@/components/Slideshow'
import { Seo } from '@/components/Seo'
import { Button } from '@/components/ui/button'
import { Container, EventVenueCard, Heading, PageHero, Pending, Prose, RoomCard, Section } from './Parts'
import { useEventVenues, useGallery, useItems, useOffers, useRoom, useRooms, useSection, useSite } from './data'
import { QueryState } from '@/components/ui/ui'
import { money } from '@/lib/utils'
import { Check, BedDouble, Ruler } from 'lucide-react'

export function About() {
  const section = useSection('about')
  const c = section.data?.content
  return (<><Seo title="About" path="/about" /><PageHero title={c?.title ?? 'About the hotel'} />
    <Section><div className="grid gap-12 lg:grid-cols-2">{c?.body ? <Prose text={c.body} /> : section.isLoading ? null : section.isError ? <p role="alert" className="text-sm text-red-700">The hotel story could not be loaded. Please try again later.</p> : <Pending what="The hotel story" />}<Img media={c?.image} className="aspect-[4/3] w-full rounded-2xl" label="About" /></div>
      {!!c?.highlights?.length && <div className="mt-14 grid gap-6 md:grid-cols-3">{c.highlights.map((h: any, i: number) => <div key={i} className="rounded-xl border border-sand bg-white p-6"><h3 className="text-2xl font-semibold text-forest-800">{h.title}</h3><p className="mt-2 text-sm text-[#4b5750]">{h.text}</p></div>)}</div>}</Section></>)
}

export function Rooms() {
  const q = useRooms()
  return (<><Seo title="Rooms & Suites" path="/rooms" /><PageHero title="Rooms & Suites" sub="Comfortable accommodation for every stay." />
    <Section><QueryState q={q as any} empty={{ show: !q.data?.length, text: 'Rooms will appear here once published by the hotel.' }}>
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">{q.data?.map((r) => <RoomCard key={r.id} room={r} shuffleImages />)}</div></QueryState></Section></>)
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
  const hasDetails = Boolean(c?.opening_hours || c?.menu_highlights?.length || c?.menu_url)
  return (<><Seo title="Restaurant & Dining" path="/restaurant" /><PageHero title={c?.title ?? 'Restaurant & Dining'} sub={c?.intro} />
    <Section>{!c ? <Pending what="Dining information" /> : <div className={hasDetails ? 'grid gap-12 lg:grid-cols-2' : ''}>{hasDetails && <div>
      {c.opening_hours && <p className="mb-6 flex items-start gap-2 text-[#38443d]"><Clock className="mt-0.5 h-5 w-5 text-gold-500" /><span className="whitespace-pre-line">{c.opening_hours}</span></p>}
      {c.menu_url && <Button asChild variant="gold" className="mb-6"><a href={c.menu_url} target="_blank" rel="noreferrer">View restaurant menu</a></Button>}
      {!!c.menu_highlights?.length && <><h2 className="mb-4 text-3xl font-semibold text-forest-800">Menu highlights</h2><ul className="divide-y divide-sand">{c.menu_highlights.map((m: any, i: number) => <li key={i} className="flex justify-between gap-4 py-3"><div><div className="font-medium">{m.name}</div><div className="text-sm text-[#5b665f]">{m.description}</div></div>{m.price_minor ? <div className="font-semibold text-forest-800">{money(m.price_minor)}</div> : null}</li>)}</ul></>}</div>}
      {!!c.images?.length && <div className={`grid gap-4 sm:grid-cols-2 self-start ${hasDetails ? '' : 'lg:grid-cols-3'}`}>{c.images.slice(0, 3).map((m: any, i: number) => <Img key={i} media={m} className="aspect-[16/10] w-full rounded-xl" label="Restaurant" />)}</div>}</div>}</Section></>)
}

export function Events() {
  const c = useSection('events').data?.content
  const items = useItems('event').data
  const venues = useEventVenues()
  const site = useSite().data
  const eventOptions = c?.services?.length ? c.services : items ?? []
  const phones: string[] = site?.profile?.phones ?? []
  return (<><Seo title="Events & Conferences" path="/events" />
    <PageHero title={c?.title ?? 'Events & Conferences'} sub="Find the right space for meetings, conferences, weddings and celebrations. Check venue availability and book by the hour." />
    <Section>
      <Heading eyebrow="Hourly venue hire" title="Choose your venue" desc="Compare capacity, hourly rates and available hours, then select a date for your event." />
      <QueryState q={venues as any} empty={{ show: venues.data?.length === 0, text: 'Event venues will appear here once they are published with an hourly rate.' }}>
        {venues.data && <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">{venues.data.map((venue: any) => <EventVenueCard key={venue.id} venue={venue} />)}</div>}
      </QueryState>
    </Section>
    {!!eventOptions.length && <Section tone="sand">
      <Heading eyebrow="Occasions" title="What are you planning?" desc="Our spaces can host a range of business gatherings and celebrations." center />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{eventOptions.map((option: any, index: number) => <article key={option.id ?? option.title ?? index} className="rounded-xl border border-sand bg-white p-5">
        <h3 className="text-xl font-semibold text-forest-800">{option.title}</h3>
        <p className="mt-2 text-sm leading-relaxed text-[#4b5750]">{option.text ?? option.body}</p>
      </article>)}</div>
    </Section>}
    <Section>
      <div className="flex flex-col gap-5 rounded-2xl bg-forest-800 p-6 text-white sm:p-8 md:flex-row md:items-center md:justify-between">
        <div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-gold-300">Need a hand?</p>
          <h2 className="mt-2 text-2xl font-semibold">Let’s plan your event</h2>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-white/80">Contact our team if you have questions about a venue, your event date or setup.</p>
        </div>
        <div className="flex flex-wrap gap-3">
          {phones[0] && <Button asChild variant="gold"><a href={`tel:${phones[0]}`}>Call {phones[0]}</a></Button>}
          <Button asChild variant="outline"><Link to="/contact">Contact us</Link></Button>
        </div>
      </div>
    </Section>
  </>)
}

export function Gallery() {
  const q = useGallery()
  const [open, setOpen] = useState<any>(null)
  return (<><Seo title="Gallery" path="/gallery" /><PageHero title="Gallery" sub="Explore New Leaders Hotel & Events Centre." />
    <Section><QueryState q={q as any} empty={{ show: !q.data?.length, text: 'No published images are available in the Media Library.' }}>
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
  const customMap = typeof c?.map_embed_url === 'string' && /^https:\/\/(www\.)?google\.[a-z.]+\/maps\/embed/.test(c.map_embed_url) ? c.map_embed_url : null
  const mapLocation = p?.latitude != null && p?.longitude != null
    ? `${p.latitude},${p.longitude}`
    : [p?.address, p?.town, p?.region, p?.country].filter(Boolean).join(', ')
  const src = customMap ?? (mapLocation ? `https://maps.google.com/maps?q=${encodeURIComponent(mapLocation)}&z=16&output=embed` : null)
  return (<><Seo title="Contact" path="/contact" /><PageHero title="Contact us" sub={c?.intro} />
    <Section>
      <div className="grid items-start gap-8 lg:grid-cols-[0.78fr_1.22fr] lg:gap-12">
        <div className="space-y-6">
          <Heading eyebrow="Reach our team" title="Get in touch" desc="For reservations, event enquiries and guest support, contact New Leaders Hotel directly." />

          <div className="divide-y divide-sand overflow-hidden rounded-2xl border border-sand bg-white shadow-sm">
            {(p?.address || p?.town) && (
              <div className="flex gap-4 p-5">
                <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-gold-300/20"><MapPin className="h-5 w-5 text-gold-500" /></span>
                <div><p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#7a847e]">Visit us</p><p className="mt-1 leading-relaxed text-[#38443d]">{[p.address, p.town, p.region, p.country].filter(Boolean).join(', ')}</p></div>
              </div>
            )}
            {!!p?.phones?.length && (
              <div className="flex gap-4 p-5">
                <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-gold-300/20"><Phone className="h-5 w-5 text-gold-500" /></span>
                <div><p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#7a847e]">Call reception</p><div className="mt-1 flex flex-col gap-1">{p.phones.map((x: string) => <a key={x} href={`tel:${x}`} className="font-medium text-forest-800 hover:text-gold-600">{x}</a>)}</div></div>
              </div>
            )}
            {!!p?.emails?.length && (
              <div className="flex gap-4 p-5">
                <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-gold-300/20"><Mail className="h-5 w-5 text-gold-500" /></span>
                <div className="min-w-0"><p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#7a847e]">Email us</p><div className="mt-1 flex flex-col gap-1">{p.emails.map((x: string) => <a key={x} href={`mailto:${x}`} className="break-all font-medium text-forest-800 hover:text-gold-600">{x}</a>)}</div></div>
              </div>
            )}
            {c?.opening_hours && (
              <div className="flex gap-4 p-5">
                <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-gold-300/20"><Clock className="h-5 w-5 text-gold-500" /></span>
                <div><p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#7a847e]">Opening hours</p><p className="mt-1 whitespace-pre-line leading-relaxed text-[#38443d]">{c.opening_hours}</p></div>
              </div>
            )}
          </div>

          {!p?.phones?.length && !p?.emails?.length && <Pending what="Contact details" />}
          {c?.directions && <Prose text={c.directions} />}
          <div className="flex flex-wrap gap-3">
            {c?.directions_url && <Button asChild variant="outline"><a href={c.directions_url} target="_blank" rel="noreferrer">Get directions</a></Button>}
            {c?.booking_url && <Button asChild variant="gold"><a href={c.booking_url} target="_blank" rel="noreferrer">Book with reception</a></Button>}
          </div>
        </div>

        <div className="overflow-hidden rounded-2xl border border-sand bg-white p-2 shadow-lg">
          {src ? (
            <iframe title="New Leaders Hotel location" src={src} className="h-[520px] w-full rounded-xl border-0 lg:h-[620px]" loading="lazy" referrerPolicy="no-referrer-when-downgrade" />
          ) : (
            <div className="grid h-[520px] place-items-center rounded-xl bg-sand text-sm text-[#7a847e] lg:h-[620px]">Map will appear once the hotel adds it.</div>
          )}
        </div>
      </div>
    </Section></>)
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
