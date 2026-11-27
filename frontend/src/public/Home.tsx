import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, BedDouble, CalendarDays, Check, Star } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Img } from '@/components/Img'
import { Container, EventVenueCard, Heading, Pending, Prose, Reveal, RoomCard, Section } from './Parts'
import { useEventVenues, useGallery, useItems, useOffers, useRooms, useSection, useSite } from './data'
import { Seo } from '@/components/Seo'

export default function Home() {
  const [videoLoaded, setVideoLoaded] = useState(false)
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
  const { data: eventVenues } = useEventVenues()

  const p = site?.profile
  const rooms = (featured?.length ? featured : allRooms)?.slice(0, 3) ?? []
  const banner = hero?.banner_images?.[0] ?? p?.banner_images?.[0]
  const roomsBackdrop = rooms[0]?.main_image ?? p?.banner_images?.[1] ?? gallery?.[1] ?? banner
  const diningImg = restaurant?.images?.[0] ?? gallery?.[4] ?? p?.banner_images?.[2] ?? banner
  return (
    <>
      <Seo path="/" />

      <section className="relative isolate flex min-h-[86svh] flex-col overflow-hidden bg-neutral-900 text-white sm:min-h-[92svh]">
        {banner ? (
          <Img media={banner} eager sizes="100vw" className={`animate-ken-burns absolute inset-0 z-0 h-full w-full object-cover transition-opacity duration-700 ${videoLoaded ? 'opacity-0' : 'opacity-100'}`} />
        ) : (
          <div className="absolute inset-0 z-0 bg-gradient-to-br from-neutral-950 via-neutral-800 to-neutral-700" aria-hidden />
        )}
        <iframe
          title="New Leaders Hotel video"
          src="https://www.youtube-nocookie.com/embed/e9jZyCXB-6I?autoplay=1&mute=1&controls=0&loop=1&playlist=e9jZyCXB-6I&playsinline=1&rel=0"
          allow="autoplay; encrypted-media; picture-in-picture"
          referrerPolicy="strict-origin-when-cross-origin"
          onLoad={() => setVideoLoaded(true)}
          className={`pointer-events-none absolute left-1/2 top-1/2 z-10 max-w-none -translate-x-1/2 -translate-y-1/2 transition-opacity duration-700 ${videoLoaded ? 'opacity-100' : 'opacity-0'}`}
          style={{ width: 'max(100%, 177.78vh)', height: 'max(100%, 56.25vw)' }}
        />
        <div className="pointer-events-none absolute inset-0 z-20 bg-gradient-to-r from-black/50 via-black/20 to-transparent" aria-hidden />
        <div className="pointer-events-none absolute inset-0 z-20 bg-gradient-to-t from-black/35 via-transparent to-transparent" aria-hidden />

        <Container className="relative z-30 flex flex-1 flex-col justify-end pb-24 pt-36 sm:pb-28 sm:pt-40">
          <div className="animate-fade-up max-w-4xl">
            <h1 className="max-w-4xl font-display text-4xl font-normal leading-tight tracking-tight sm:text-5xl">
              {hero?.headline ?? 'A warm welcome in Akyem Tafo'}
            </h1>
          </div>
        </Container>
      </section>

      <section className="relative z-10 -mt-10 px-4 sm:px-6">
        <div className="mx-auto flex max-w-4xl flex-col items-center gap-5 rounded-2xl border border-sand bg-white px-5 py-6 shadow-xl sm:px-8 sm:py-7 md:flex-row md:justify-between">
          <div className="text-center md:text-left">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-gold-600">Make a booking</p>
            <p className="mt-1 text-sm text-[#5b665f]">Choose what you would like to book.</p>
          </div>
          <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
            <Button asChild variant="outline" size="lg" className="w-full border-forest-700 text-forest-800 sm:w-auto">
              <Link to="/booking/search"><BedDouble className="h-4 w-4" />Book a room</Link>
            </Button>
            <Button asChild variant="gold" size="lg" className="w-full sm:w-auto">
              <Link to="/events/book"><CalendarDays className="h-4 w-4" />Book the event centre</Link>
            </Button>
          </div>
        </div>
      </section>

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
              Comfortable rooms with modern conveniences, cozy mattresses and city views. Contact our team for current room details and rates.
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

      <Section>
        <div className="grid items-center gap-12 lg:grid-cols-2">
          <div>
            <Heading
              eyebrow="Culinary"
              title={restaurant?.title ?? 'Restaurants & Dining'}
              desc={restaurant?.intro || 'Enjoy local cuisine at our on-site restaurant, then unwind at the rooftop bar and lounge with city views.'}
            />
            <Button asChild variant="default">
              <Link to="/restaurant">Explore dining <ArrowRight className="h-4 w-4" /></Link>
            </Button>
          </div>
          <Img media={diningImg} className="aspect-[16/10] w-full rounded-2xl object-cover shadow-md" label="Restaurant & Dining" />
        </div>
      </Section>

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

      <Section tone="sand">
        <Heading
          eyebrow="Conferences & Celebrations"
          title={events?.title ?? 'Meetings & Events'}
          desc="From meetings and conferences to engagements, weddings and parties, choose a venue that fits your event and book the date and hours that work for you."
        />
        {eventVenues?.length ? (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {eventVenues.map((venue: any) => <EventVenueCard key={venue.id} venue={venue} />)}
          </div>
        ) : (
          <Pending what="Event venues" />
        )}
        <div className="mt-8 text-center">
          <Button asChild variant="outline"><Link to="/events">Explore event details <ArrowRight className="h-4 w-4" /></Link></Button>
        </div>
      </Section>

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
