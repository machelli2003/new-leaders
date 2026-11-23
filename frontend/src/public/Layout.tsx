import { useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { Menu, X, Phone, Mail, MapPin, Facebook, Instagram, Youtube, MessageCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Img } from '@/components/Img'
import { Seo } from '@/components/Seo'
import { useSection, useSite } from './data'
import { usePreview } from '@/lib/hooks'
import { cn } from '@/lib/utils'

const NAV = [['/', 'Home'], ['/about', 'About'], ['/rooms', 'Rooms'], ['/facilities', 'Facilities'], ['/restaurant', 'Dining'], ['/events', 'Events'], ['/gallery', 'Gallery'], ['/offers', 'Offers'], ['/contact', 'Contact']]

export function Brand({ light }: { light?: boolean }) {
  const { data } = useSite()
  const p = data?.profile
  return (
    <Link to="/" className="flex items-center gap-3" aria-label={`${p?.name ?? 'New Leaders Hotel'} home`}>
      {p?.logo_image ? <Img media={p.logo_image} eager className="h-10 w-auto max-w-[120px] object-contain" /> :
        <span className="grid h-10 w-10 place-items-center rounded-full bg-forest-800 font-serif text-lg text-gold-400">NL</span>}
      <span className={cn('font-serif text-xl font-semibold leading-tight', light ? 'text-white' : 'text-forest-800')}>{p?.name ?? 'New Leaders Hotel'}
        {p?.branch_name && <span className="block font-sans text-[10px] font-medium uppercase tracking-[0.18em] text-gold-500">{p.branch_name}</span>}</span>
    </Link>
  )
}

function ComingSoon() {
  const { data } = useSite()
  const p = data?.profile
  return (
    <div className="grid min-h-screen place-items-center bg-forest-900 p-6 text-center text-white">
      <div className="max-w-md space-y-4"><div className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-forest-700 font-serif text-2xl text-gold-400">NL</div>
        <h1 className="text-4xl font-semibold">{p?.name ?? 'New Leaders Hotel'}</h1><p className="text-gold-300">{p?.branch_name}</p>
        <p className="text-white/80">Our new website is on its way. Please check back soon.</p>
        {p?.phones?.[0] && <p className="text-sm text-white/70">Call us: {p.phones[0]}</p>}</div>
    </div>
  )
}

export function PublicLayout() {
  const [open, setOpen] = useState(false)
  const { data: site, isLoading } = useSite()
  const preview = usePreview()
  const { data: footer } = useSection('footer')
  if (isLoading) return <div className="grid min-h-screen place-items-center text-sm text-[var(--muted)]">Loading…</div>
  if (site && !site.published) return <><Seo noindex /><ComingSoon /></>
  const p = site?.profile
  const s = p?.socials ?? {}
  return (
    <div className="min-h-screen bg-ivory text-[#1c2420]">
      <Seo />
      <a href="#main" className="skip-link">Skip to content</a>
      {preview && <div className="bg-gold-500 px-4 py-1.5 text-center text-xs font-medium text-white">Preview mode: showing unpublished drafts. <a className="underline" href="?preview=0">Exit preview</a></div>}
      {site?.has_sample_content && <div className="bg-amber-100 px-4 py-1.5 text-center text-xs text-amber-900">Sample content: rooms and prices shown are placeholders, not confirmed hotel information.</div>}
      <header className="sticky top-0 z-40 border-b border-sand bg-ivory/95 backdrop-blur">
        <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-4 sm:px-6">
          <Brand />
          <nav aria-label="Main" className="hidden items-center gap-6 lg:flex">
            {NAV.map(([to, label]) => <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => cn('text-sm font-medium transition-colors hover:text-gold-600', isActive ? 'text-gold-600' : 'text-forest-800')}>{label}</NavLink>)}
          </nav>
          <div className="flex items-center gap-2">
            <Button asChild variant="gold" className="hidden sm:inline-flex"><Link to="/booking/search">Book now</Link></Button>
            <button className="rounded p-2 lg:hidden" aria-label="Menu" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? <X /> : <Menu />}</button>
          </div>
        </div>
        {open && <nav aria-label="Mobile" className="border-t border-sand bg-ivory px-4 py-3 lg:hidden">
          {[...NAV, ['/booking/search', 'Book now'], ['/booking/lookup', 'Find my booking']].map(([to, label]) => <Link key={to} to={to} onClick={() => setOpen(false)} className="block rounded px-2 py-2.5 text-sm font-medium text-forest-800 hover:bg-sand">{label}</Link>)}
        </nav>}
      </header>
      <main id="main"><Outlet /></main>
      <footer className="bg-forest-900 text-white/80">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-14 sm:px-6 md:grid-cols-4">
          <div className="md:col-span-2 space-y-3"><Brand light /><p className="max-w-md text-sm leading-relaxed">{footer?.content?.about ?? p?.description}</p>
            <div className="flex gap-3 pt-2">
              {s.facebook && <a aria-label="Facebook" href={s.facebook} target="_blank" rel="noreferrer noopener"><Facebook className="h-5 w-5" /></a>}
              {s.instagram && <a aria-label="Instagram" href={s.instagram} target="_blank" rel="noreferrer noopener"><Instagram className="h-5 w-5" /></a>}
              {s.youtube && <a aria-label="YouTube" href={s.youtube} target="_blank" rel="noreferrer noopener"><Youtube className="h-5 w-5" /></a>}
              {s.whatsapp && <a aria-label="WhatsApp" href={s.whatsapp} target="_blank" rel="noreferrer noopener"><MessageCircle className="h-5 w-5" /></a>}
            </div></div>
          <div><h3 className="mb-3 font-serif text-lg text-gold-400">Explore</h3><ul className="space-y-2 text-sm">{[['/rooms', 'Rooms'], ['/restaurant', 'Dining'], ['/events', 'Events'], ['/offers', 'Offers'], ['/faq', 'FAQs'], ['/booking/lookup', 'Find my booking']].map(([to, l]) => <li key={to}><Link className="hover:text-gold-300" to={to}>{l}</Link></li>)}</ul></div>
          <div><h3 className="mb-3 font-serif text-lg text-gold-400">Contact</h3><ul className="space-y-2 text-sm">
            {(p?.address || p?.town) && <li className="flex gap-2"><MapPin className="mt-0.5 h-4 w-4 shrink-0" />{[p.address, p.town, p.region].filter(Boolean).join(', ')}</li>}
            {p?.phones?.map((x: string) => <li key={x} className="flex gap-2"><Phone className="mt-0.5 h-4 w-4" /><a href={`tel:${x}`}>{x}</a></li>)}
            {p?.emails?.map((x: string) => <li key={x} className="flex gap-2"><Mail className="mt-0.5 h-4 w-4" /><a href={`mailto:${x}`}>{x}</a></li>)}
            {!p?.phones?.length && !p?.emails?.length && <li className="text-white/50">Contact details coming soon</li>}</ul></div>
        </div>
        <div className="border-t border-white/10 px-4 py-5 text-center text-xs text-white/60">
          <span>{footer?.content?.copyright ?? `© ${new Date().getFullYear()} ${p?.name ?? ''}`}</span>
          <span className="mx-2">·</span><Link to="/privacy-policy">Privacy</Link><span className="mx-2">·</span><Link to="/terms">Terms</Link><span className="mx-2">·</span><Link to="/cancellation-policy">Cancellation</Link>
        </div>
      </footer>
    </div>
  )
}
