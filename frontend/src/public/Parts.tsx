import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, BedDouble, Clock, Users } from 'lucide-react'
import { Img } from '@/components/Img'
import { Button } from '@/components/ui/button'
import { Field, Input, Select } from '@/components/ui/form'
import { Card } from '@/components/ui/ui'
import { addDays, isoToday, money } from '@/lib/utils'

export const Container = ({ children, className = '' }: { children: ReactNode; className?: string }) => <div className={`mx-auto max-w-7xl px-4 sm:px-6 ${className}`}>{children}</div>

export function Reveal({ children, className = '' }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const [shown, setShown] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el || typeof IntersectionObserver === 'undefined') { setShown(true); return }
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setShown(true); io.disconnect() } }, { threshold: 0.08 })
    io.observe(el)
    return () => io.disconnect()
  }, [])
  return (
    <div ref={ref} className={`transition-all duration-700 ease-out ${shown ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0'} ${className}`}>
      {children}
    </div>
  )
}

export const Section = ({ children, className = '', tone }: { children: ReactNode; className?: string; tone?: 'sand' | 'dark' }) =>
  <section className={`py-16 sm:py-20 ${tone === 'sand' ? 'bg-sand/60' : tone === 'dark' ? 'bg-forest-800 text-white' : ''} ${className}`}><Container><Reveal>{children}</Reveal></Container></section>
export function Heading({ eyebrow, title, desc, center, light }: { eyebrow?: string; title: string; desc?: string; center?: boolean; light?: boolean }) {
  return (
    <div className={`mb-10 max-w-2xl ${center ? 'mx-auto text-center' : ''}`}>
      {eyebrow && <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-gold-500">{eyebrow}</p>}
      <h2 className={`text-4xl font-semibold sm:text-5xl ${light ? 'text-white' : 'text-forest-800'}`}>{title}</h2>
      {desc && <p className={`mt-4 leading-relaxed ${light ? 'text-white/80' : 'text-[#4b5750]'}`}>{desc}</p>}
    </div>
  )
}
export function PageHero({ title, sub }: { title: string; sub?: string }) {
  return <div className="bg-forest-800 py-12 text-center text-white sm:py-16"><Container className="animate-fade-up"><h1 className="break-words text-4xl font-semibold sm:text-5xl">{title}</h1>{sub && <p className="mx-auto mt-3 max-w-2xl text-white/80">{sub}</p>}</Container></div>
}
export const Prose = ({ text }: { text?: string }) => <div className="max-w-3xl space-y-4 leading-relaxed text-[#38443d]">{(text ?? '').split(/\n{2,}/).filter(Boolean).map((p, i) => <p key={i}>{p}</p>)}</div>
export const Pending = ({ what }: { what: string }) => <p className="rounded-lg border border-dashed border-gold-400 bg-gold-300/10 p-6 text-center text-sm text-[#6b5a2e]">{what} will appear here once the hotel publishes it from the dashboard.</p>

export function BookingBar({ compact, initial }: { compact?: boolean; initial?: Record<string, string> }) {
  const nav = useNavigate()
  const [f, setF] = useState({ check_in: initial?.check_in ?? addDays(isoToday(), 1), check_out: initial?.check_out ?? addDays(isoToday(), 2), adults: initial?.adults ?? '2', children: initial?.children ?? '0', rooms: initial?.rooms ?? '1' })
  const set = (k: string) => (e: any) => setF((s) => {
    const n = { ...s, [k]: e.target.value }
    if (k === 'check_in' && n.check_out <= n.check_in) n.check_out = addDays(n.check_in, 1)
    return n
  })
  const submit = (e: FormEvent) => { e.preventDefault(); nav(`/booking/search?${new URLSearchParams(f).toString()}`) }
  return (
    <form onSubmit={submit} className={`grid gap-3 text-[#1c2420] sm:grid-cols-2 lg:grid-cols-6 ${compact ? 'bg-transparent p-0 shadow-none' : 'rounded-xl bg-white p-4 shadow-xl'}`} aria-label="Check availability">
      <Field label="Check-in"><Input type="date" required min={isoToday()} value={f.check_in} onChange={set('check_in')} /></Field>
      <Field label="Check-out"><Input type="date" required min={addDays(f.check_in, 1)} value={f.check_out} onChange={set('check_out')} /></Field>
      <Field label="Adults"><Select value={f.adults} onChange={set('adults')}>{[1, 2, 3, 4, 5, 6, 8, 10].map((n) => <option key={n}>{n}</option>)}</Select></Field>
      <Field label="Children"><Select value={f.children} onChange={set('children')}>{[0, 1, 2, 3, 4, 5, 6].map((n) => <option key={n}>{n}</option>)}</Select></Field>
      <Field label="Rooms"><Select value={f.rooms} onChange={set('rooms')}>{[1, 2, 3, 4, 5].map((n) => <option key={n}>{n}</option>)}</Select></Field>
      <div className="flex items-end"><Button type="submit" variant="gold" className="w-full">Check availability</Button></div>
    </form>
  )
}

export function RoomCard({ room, shuffleImages = false }: { room: any; shuffleImages?: boolean }) {
  const images = useMemo(() => {
    const seen = new Set<string>()
    return [room.main_image, ...(room.gallery_images ?? [])].filter((image: any) => {
      if (!image) return false
      const key = image.id ?? image.url
      if (!key || seen.has(key)) return false
      seen.add(key)
      return true
    })
  }, [room.main_image, room.gallery_images])
  const [imageTransition, setImageTransition] = useState({ current: 0, previous: 0 })

  useEffect(() => {
    setImageTransition({ current: 0, previous: 0 })
    if (!shuffleImages || images.length < 2 || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

    const shuffledIndices = (previousImage?: number) => {
      const indices = images.map((_: unknown, index: number) => index)
      for (let i = indices.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1))
        const value = indices[i]
        indices[i] = indices[j]
        indices[j] = value
      }
      if (previousImage !== undefined && indices[0] === previousImage) {
        const value = indices[0]
        indices[0] = indices[1]
        indices[1] = value
      }
      return indices
    }

    let order = shuffledIndices()
    let next = 1
    setImageTransition({ current: order[0], previous: 0 })
    const interval = window.setInterval(() => {
      if (next >= order.length) {
        order = shuffledIndices(order[order.length - 1])
        next = 0
      }
      const nextImage = order[next]
      setImageTransition((current) => ({ current: nextImage, previous: current.current }))
      next += 1
    }, 4000)
    return () => window.clearInterval(interval)
  }, [images, shuffleImages])

  return (
    <Card className="group overflow-hidden border-sand bg-white transition-all duration-300 hover:-translate-y-1 hover:shadow-lg">
      <Link to={`/rooms/${room.slug}`} className="relative block aspect-[4/3] overflow-hidden">
        <Img media={images[imageTransition.previous]} className="absolute inset-0 h-full w-full" sizes="(min-width:1024px) 33vw, 100vw" label={room.name} />
        <Img key={imageTransition.current} media={images[imageTransition.current]} className="animate-room-image absolute inset-0 h-full w-full" sizes="(min-width:1024px) 33vw, 100vw" label={room.name} />
      </Link>
      <div className="space-y-3 p-5">
        <div className="flex items-start justify-between gap-3"><h3 className="text-2xl font-semibold text-forest-800">{room.name}</h3>
          {room.is_sample && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-amber-800">Sample</span>}</div>
        <p className="line-clamp-2 text-sm text-[#4b5750]">{room.short_description}</p>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-[#5b665f]"><span className="flex items-center gap-1"><Users className="h-3.5 w-3.5" />Up to {room.max_occupancy} guests</span>{room.bed_configuration && <span className="flex items-center gap-1"><BedDouble className="h-3.5 w-3.5" />{room.bed_configuration}</span>}</div>
        {room.amenities?.length > 0 && <p className="line-clamp-1 text-xs text-[#5b665f]">{room.amenities.slice(0, 4).map((a: any) => a.name).join(' · ')}</p>}
        <div className="flex items-center justify-between border-t border-sand pt-3">
          <div>{room.default_rate_minor ? <><span className="text-[11px] uppercase text-[#7a847e]">From</span><div className="text-lg font-semibold text-forest-800">{money(room.default_rate_minor)}<span className="text-xs font-normal text-[#7a847e]"> / night</span></div></> : <span className="text-sm text-[#7a847e]">Rate on request</span>}</div>
          <Button asChild variant="outline" size="sm"><Link to={`/rooms/${room.slug}`}>Details <ArrowRight className="h-3.5 w-3.5" /></Link></Button>
        </div>
      </div>
    </Card>
  )
}

export function EventVenueCard({ venue }: { venue: any }) {
  const bookingPath = `/events/book?venue=${encodeURIComponent(venue.id)}`

  return (
    <Card className="group overflow-hidden border-sand bg-white transition-all duration-300 hover:-translate-y-1 hover:shadow-lg">
      <Link to={bookingPath} className="relative block aspect-[4/3] overflow-hidden">
        <Img media={venue.main_image} className="absolute inset-0 h-full w-full" sizes="(min-width:1024px) 33vw, 100vw" label={venue.name} />
      </Link>
      <div className="space-y-3 p-5">
        <h3 className="text-2xl font-semibold text-forest-800">{venue.name.trim()}</h3>
        {venue.description && <p className="line-clamp-2 text-sm text-[#4b5750]">{venue.description}</p>}
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-[#5b665f]">
          <span className="flex items-center gap-1"><Users className="h-3.5 w-3.5" />Up to {venue.capacity} guests</span>
          <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" />{venue.opening_time}–{venue.closing_time}</span>
        </div>
        <div className="flex items-center justify-between border-t border-sand pt-3">
          <div><span className="text-[11px] uppercase text-[#7a847e]">From</span><div className="text-lg font-semibold text-forest-800">{money(venue.hourly_rate_minor)}<span className="text-xs font-normal text-[#7a847e]"> / hour</span></div></div>
          <Button asChild variant="outline" size="sm"><Link to={bookingPath}>Book venue <ArrowRight className="h-3.5 w-3.5" /></Link></Button>
        </div>
      </div>
    </Card>
  )
}
