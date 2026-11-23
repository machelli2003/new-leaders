import { Link } from 'react-router-dom'
import { ArrowRight, Check, Clock, MapPin, Phone, Star } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Img } from '@/components/Img'
import { BookingBar, Container, Heading, Pending, Prose, Reveal, RoomCard, Section } from './Parts'
import { useGallery, useItems, useOffers, useRooms, useSection, useSite } from './data'
import { Seo } from '@/components/Seo'

export default function Home() {
  const { data: site } = useSite()
  const hero = useSection('home.hero').data?.content
  const intro = useSection('home.intro').data?.content
  const restaurant = useSection('restaurant').data?.content
  const events = useSection('events').data?.content
  const { data: featured } = useRooms(true)
  const { data: allRooms } = useRooms(false)
  const { data: facilities } = useItems('facility')
  const { data: gallery } = useGallery()
  const { data: offers } = useOffers()
  const { data: testimonials } = useItems('testimonial')

  const p = site?.profile
  const rooms = (featured?.length ? featured : allRooms)?.slice(0, 3) ?? []
  const banner = hero?.banner_images?.[0] ?? p?.banner_images?.[0]
  const roomsBackdrop = rooms[0]?.main_image ?? p?.banner_images?.[1] ?? gallery?.[1] ?? banner
  const diningImg = restaurant?.images?.[0] ?? gallery?.[4] ?? p?.banner_images?.[2] ?? banner
  const eventsImg = events?.images?.[0] ?? gallery?.[5] ?? p?.banner_images?.[1] ?? banner

  return (
    <>
      <Seo path="/" />

      {/* 1. KEMPINSKI-STYLE FULL-SCREEN HERO WITH CENTERED HEADLINE & BOTTOM BOOKING BAR */}
      <section className="relative isolate flex min-h-screen flex-col overflow-hidden bg-forest-900 text-white">
        {banner ? (
          <Img media={banner} eager sizes="100vw" className="animate-ken-burns absolute inset-0 -z-10 h-full w-full object-cover opacity-70" />
        ) : (
          <div className="absolute inset-0 -z-10 bg-gradient-to-br from-forest-900 via-forest-800 to-forest-600" aria-hidden />
        )}
        <div className="absolute inset-0 -z-10 bg-gradient-to-b from-forest-900/45 via-black/25 to-forest-900/85" aria-hidden />

        <Container className="flex flex-1 flex-col justify-between pb-24 pt-32 sm:pt-40">
          <div className="animate-fade-up mx-auto max-w-4xl text-center">
            <p className="mb-4 text-xs font-semibold uppercase tracking-[0.28em] text-gold-300">
              {p?.branch_name || `${p?.town ?? ''} · ${p?.country ?? ''}`}
            </p>
            <h1 className="text-5xl font-semibold leading-[1.05] tracking-tight sm:text-7xl">
              {hero?.headline ?? 'Where Excellent Service Meets Luxury'}
            </h1>
            <p className="mx-auto mt-5 max-w-2xl text-base text-white/90 sm:text-lg">
              {hero?.subheadline ?? p?.description}
            </p>
          </div>
          <div className="animate-fade-up mt-auto pt-12" style={{ animationDelay: '150ms' }}>
            <BookingBar />
          </div>
        </Container>
      </section>

      {/* 2. KEMPINSKI-STYLE ASYMMETRIC HOTEL INTRO + LOCATION DETAILS */}
      <Section>
        <div className="flex flex-col justify-between gap-10 md:flex-row md:items-start">
          <div className="md:w-7/12">
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.22em] text-gold-500">Welcome</p>
            <h2 className="text-4xl font-semibold leading-tight text-forest-800 sm:text-5xl">
              {intro?.title ?? p?.name ?? 'New Leaders Hotel & Events Centre'}
            </h2>
            <div className="mt-6">
              {intro?.body ? <Prose text={intro.body} /> : <p className="leading-relaxed text-[#4b5750]">{p?.description}</p>}
            </div>
            <div className="mt-7 flex flex-wrap gap-3">
              <Button asChild variant="outline">
                <Link to="/about">Discover our story <ArrowRight className="h-4 w-4" /></Link>
              </Button>
              <Button asChild variant="gold">
                <Link to="/booking/search">Reserve a room</Link>
              </Button>
            </div>
          </div>

          <div className="rounded-2xl border border-sand bg-sand/50 p-7 md:w-4/12">
            <h3 className="text-2xl font-semibold text-forest-800">Hotel Details</h3>
            <ul className="mt-5 space-y-4 text-sm text-[#38443d]">
              {(p?.address || p?.town) && (
                <li className="flex gap-3">
                  <MapPin className="mt-0.5 h-5 w-5 shrink-0 text-gold-500" />
                  <span>{[p.address, p.town, p.region, p.country].filter(Boolean).join(', ')}</span>
                </li>
              )}
              {p?.phones?.length > 0 && (
                <li className="flex gap-3">
                  <Phone className="mt-0.5 h-5 w-5 shrink-0 text-gold-500" />
                  <div className="flex flex-col gap-1">
                    {p.phones.map((x: string) => (
                      <a key={x} href={`tel:${x}`} className="font-medium hover:text-gold-500">{x}</a>
                    ))}
                  </div>
                </li>
              )}
              {site?.booking && (
                <li className="flex gap-3">
                  <Clock className="mt-0.5 h-5 w-5 shrink-0 text-gold-500" />
                  <span>Check-in from {site.booking.check_in_time} · Check-out by {site.booking.check_out_time}</span>
                </li>
              )}
            </ul>
            <Button asChild variant="default" className="mt-6 w-full">
              <Link to="/contact">Get directions & contact</Link>
            </Button>
          </div>
        </div>
      </Section>

      {/* 3. SPECIAL OFFERS (KEMPINSKI CAROUSEL / GRID) */}
      {!!offers?.length && (
        <Section tone="sand">
          <Heading eyebrow="Exclusive" title="Special Offers" desc="Make the most of your stay with our seasonal packages." center />
          <div className="grid gap-6 md:grid-cols-2">
            {offers.slice(0, 2).map((o) => (
              <div key={o.id} className="group overflow-hidden rounded-2xl border border-sand bg-white shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-lg md:flex">
                <Img media={o.image} className="h-52 w-full object-cover md:h-auto md:w-2/5" />
                <div className="flex flex-col justify-between p-6">
                  <div>
                    <h3 className="text-2xl font-semibold text-forest-800">{o.title}</h3>
                    <p className="mt-2 text-sm text-[#4b5750]">{o.description}</p>
                    {o.code && !o.hide_code && (
                      <p className="mt-3 text-sm">
                        Promo code: <b className="rounded bg-gold-300/25 px-2 py-0.5 text-gold-600">{o.code}</b>
                      </p>
                    )}
                  </div>
                  <Button asChild variant="outline" size="sm" className="mt-4 self-start">
                    <Link to="/offers">View Offer <ArrowRight className="h-3.5 w-3.5" /></Link>
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* 4. FULL-BLEED ROOMS & SUITES BANNER + ROOM CARDS (KEMPINSKI SIGNATURE SECTION) */}
      <section className="relative isolate overflow-hidden bg-forest-900 py-24 text-center text-white">
        {roomsBackdrop && (
          <Img media={roomsBackdrop} className="absolute inset-0 -z-10 h-full w-full object-cover opacity-40" sizes="100vw" />
        )}
        <div className="absolute inset-0 -z-10 bg-gradient-to-b from-forest-900/60 to-forest-900/85" aria-hidden />
        <Container>
          <Reveal>
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.25em] text-gold-300">Accommodation</p>
            <h2 className="text-5xl font-semibold sm:text-6xl">Rooms & Suites</h2>
            <p className="mx-auto mt-4 max-w-xl text-white/85">
              Thoughtfully designed rooms with cozy mattresses, modern conveniences, and serene views for solo travellers, couples, and families.
            </p>
            <Button asChild variant="gold" size="lg" className="mt-7">
              <Link to="/rooms">Explore All Rooms</Link>
            </Button>
          </Reveal>
        </Container>
      </section>

      <Section tone="sand">
        {rooms.length ? (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {rooms.map((r) => <RoomCard key={r.id} room={r} />)}
          </div>
        ) : (
          <Pending what="Room categories" />
        )}
      </Section>

      {/* 5. RESTAURANTS & DINING (50/50 EDITORIAL SPLIT) */}
      <Section>
        <div className="grid items-center gap-12 lg:grid-cols-2">
          <div>
            <Heading
              eyebrow="Culinary"
              title={restaurant?.title ?? 'Restaurants & Dining'}
              desc={restaurant?.intro || 'From authentic Ghanaian cuisine in our on-site restaurant to drinks and city views at our rooftop bar and lounge.'}
            />
            <Button asChild variant="default">
              <Link to="/restaurant">Explore dining <ArrowRight className="h-4 w-4" /></Link>
            </Button>
          </div>
          <Img media={diningImg} className="aspect-[16/10] w-full rounded-2xl object-cover shadow-md" label="Restaurant & Dining" />
        </div>
      </Section>

      {/* 6. FACILITIES & SERVICES (CENTERED EDITORIAL + GRID) */}
      <Section tone="sand">
        <Heading
          eyebrow="Hospitality & Comfort"
          title="Facilities & Services"
          desc="Everything you need for a seamless, relaxing stay in Akyem Tafo."
          center
        />
        {facilities?.length ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {facilities.slice(0, 8).map((f) => (
              <div key={f.id} className="flex gap-3 rounded-xl border border-sand bg-white p-5 shadow-xs transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md">
                <Check className="mt-0.5 h-5 w-5 shrink-0 text-gold-500" />
                <div>
                  <h3 className="font-sans text-base font-semibold text-forest-800">{f.title}</h3>
                  {f.body && <p className="mt-1 line-clamp-2 text-sm text-[#5b665f]">{f.body}</p>}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <Pending what="Facilities" />
        )}
        <div className="mt-8 text-center">
          <Button asChild variant="outline"><Link to="/facilities">All facilities</Link></Button>
        </div>
      </Section>

      {/* 7. MEETINGS & EVENTS (KEMPINSKI EDITORIAL SPLIT) */}
      <Section>
        <div className="grid items-center gap-12 lg:grid-cols-2">
          <Img media={eventsImg} className="aspect-[16/10] w-full rounded-2xl object-cover shadow-md lg:order-first" label="Meetings & Events" />
          <div>
            <Heading
              eyebrow="Conferences & Celebrations"
              title={events?.title ?? 'Meetings & Events'}
              desc={events?.intro || 'With versatile event spaces and dedicated hospitality, we host corporate conferences, weddings, and unforgettable celebrations.'}
            />
            <div className="flex flex-wrap gap-3">
              <Button asChild variant="gold">
                <Link to="/events">Plan your event <ArrowRight className="h-4 w-4" /></Link>
              </Button>
              <Button asChild variant="outline">
                <Link to="/contact">Enquire now</Link>
              </Button>
            </div>
          </div>
        </div>
      </Section>

      {/* 8. MOVING GALLERY SLIDESHOW */}
      {!!gallery?.length && (
        <Section tone="sand">
          <Heading eyebrow="Gallery" title="A Glimpse of New Leaders Hotel" desc="Explore our rooms, grounds, dining, and event spaces." center />
          <div className="overflow-hidden rounded-xl py-2">
            <div className="animate-marquee gap-4">
              {[...gallery.slice(0, 10), ...gallery.slice(0, 10)].map((g, i) => (
                <Link key={`${g.id}-${i}`} to="/gallery" className="group h-56 w-72 shrink-0 overflow-hidden rounded-xl shadow-sm sm:h-64 sm:w-80">
                  <Img media={g} className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105" sizes="320px" />
                </Link>
              ))}
            </div>
          </div>
          <div className="mt-8 text-center">
            <Button asChild variant="default"><Link to="/gallery">Open full gallery slideshow</Link></Button>
          </div>
        </Section>
      )}

      {/* 9. GUEST TESTIMONIALS */}
      {!!testimonials?.length && (
        <Section>
          <Heading eyebrow="Guests" title="What Guests Say" center />
          <div className="grid gap-6 md:grid-cols-3">
            {testimonials.map((t) => (
              <figure key={t.id} className="rounded-xl border border-sand bg-white p-6 shadow-xs">
                <div className="mb-2 flex text-gold-500">
                  {[...Array(5)].map((_, i) => <Star key={i} className="h-4 w-4 fill-current" />)}
                </div>
                <blockquote className="text-sm leading-relaxed text-[#38443d]">“{t.body}”</blockquote>
                <figcaption className="mt-3 text-sm font-medium text-forest-800">{t.author || t.title}</figcaption>
              </figure>
            ))}
          </div>
        </Section>
      )}

      {/* 10. FINAL BOOKING CTA BAND */}
      <Section tone="dark">
        <div className="flex flex-col items-center justify-between gap-6 text-center md:flex-row md:text-left">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.22em] text-gold-300">Book Direct</p>
            <h2 className="text-4xl font-semibold sm:text-5xl">Ready for an Unforgettable Stay?</h2>
            <p className="mt-2 max-w-xl text-white/80">
              Check live availability and reserve your room at New Leaders Hotel & Events Centre in minutes.
            </p>
          </div>
          <Button asChild variant="gold" size="lg" className="shrink-0">
            <Link to="/booking/search">Book your stay <ArrowRight className="h-4 w-4" /></Link>
          </Button>
        </div>
      </Section>
    </>
  )
}
