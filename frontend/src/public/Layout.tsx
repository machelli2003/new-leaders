import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { Menu, X, Phone, Mail, MapPin, Facebook, Instagram, Youtube, MessageCircle } from 'lucide-react'
import { Img } from '@/components/Img'
import { Seo } from '@/components/Seo'
import { useSection, useSite } from './data'
import { usePreview } from '@/lib/hooks'
import { cn } from '@/lib/utils'

const PRIMARY_NAV = [['/', 'Home'], ['/rooms', 'Rooms'], ['/restaurant', 'Dining'], ['/events', 'Events'], ['/contact', 'Contact']] as const
const DISCOVER_NAV = [['/about', 'About the hotel'], ['/facilities', 'Facilities'], ['/gallery', 'Gallery'], ['/offers', 'Special offers']] as const

export function Brand({ light, centered = false }: { light?: boolean; centered?: boolean }) {
  const { data } = useSite()
  const p = data?.profile
  const centeredNameParts = p?.name?.match(/^(.*?)\s+(Hotel\b.*)$/i)
  const brandName = centered && centeredNameParts ? centeredNameParts[1] : p?.name ?? 'New Leaders Hotel'
  const branchName = centered && centeredNameParts
    ? [centeredNameParts[2], p?.branch_name?.replace(/\s+Branch$/i, '')].filter(Boolean).join(' · ')
    : p?.branch_name
  return (
    <Link to="/" className={cn('flex items-center gap-3', centered && 'absolute left-1/2 top-1/2 z-0 w-max max-w-[42vw] -translate-x-1/2 -translate-y-1/2 flex-col justify-center gap-0 text-center sm:max-w-[280px]')} aria-label={`${p?.name ?? 'New Leaders Hotel'} home`}>
      {!centered && (p?.logo_image ? <Img media={p.logo_image} eager className="h-10 w-auto max-w-[120px] object-contain" /> :
        <span className="grid h-10 w-10 place-items-center rounded-full bg-forest-800 font-serif text-lg text-gold-400">NL</span>)}
      <span className={cn('font-serif font-semibold leading-tight', centered ? 'text-[14px] uppercase tracking-[0.08em] sm:text-xl' : 'text-xl', light ? 'text-white' : 'text-forest-800')}>{brandName}
        {branchName && <span className={cn('block truncate font-sans font-medium uppercase', centered ? 'w-full text-[7px] tracking-[0.12em] sm:text-[9px]' : 'text-[10px] tracking-[0.18em]', light ? 'text-gold-300' : 'text-gold-500')}>{branchName}</span>}</span>
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
  const [scrolled, setScrolled] = useState(false)
  const location = useLocation()
  const isHome = location.pathname === '/'
  const homeOverlay = isHome && !scrolled
  const { data: site } = useSite()
  const preview = usePreview()
  const { data: footer } = useSection('footer')
  useEffect(() => {
    if (!isHome) {
      setScrolled(false)
      return
    }
    const updateScroll = () => setScrolled(window.scrollY > 24)
    updateScroll()
    window.addEventListener('scroll', updateScroll, { passive: true })
    return () => window.removeEventListener('scroll', updateScroll)
  }, [isHome])
  useEffect(() => {
    setOpen(false)
  }, [location.pathname])
  if (site && !site.published) return <><Seo noindex /><ComingSoon /></>
  const p = site?.profile
  const s = p?.socials ?? {}
  return (
    <div className="min-h-screen bg-ivory text-[#1c2420]">
      <Seo />
      <a href="#main" className="skip-link">Skip to content</a>
      {preview && <div className="bg-gold-500 px-4 py-1.5 text-center text-xs font-medium text-white">Preview mode: showing unpublished drafts. <a className="underline" href="?preview=0">Exit preview</a></div>}
      {site?.has_sample_content && <div className="bg-amber-100 px-4 py-1.5 text-center text-xs text-amber-900">Sample content: rooms and prices shown are placeholders, not confirmed hotel information.</div>}
      <header className={cn(
        'z-40 w-full transition-all duration-300',
        isHome
          ? cn('fixed inset-x-0 top-0', homeOverlay ? 'bg-transparent shadow-none' : 'bg-ivory/95 shadow-md backdrop-blur-xl')
          : 'sticky top-0 bg-ivory/95 shadow-sm backdrop-blur-xl',
      )}>
        <div className="relative mx-auto flex h-16 w-full items-center justify-between px-4 sm:h-20 sm:px-7 lg:px-9">
          <button type="button" aria-label={open ? 'Close menu' : 'Open menu'} aria-expanded={open} aria-controls={open ? 'site-menu' : undefined} onClick={() => setOpen((value) => !value)} className={cn('relative z-10 inline-flex w-fit items-center gap-2 py-2 text-xs font-semibold uppercase tracking-[0.12em] transition-colors', homeOverlay ? 'text-white hover:text-gold-300' : 'text-forest-800 hover:text-gold-600')}>
            {open ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            <span>{open ? 'Close' : 'Menu'}</span>
          </button>
          <Brand centered light={homeOverlay} />
          <div className={cn('relative z-10 flex min-w-0 items-center justify-end gap-2 sm:gap-4 lg:gap-6', homeOverlay ? 'text-white' : 'text-forest-800')}>
            <Link to="/contact" className="hidden text-xs font-medium uppercase tracking-[0.08em] transition-colors hover:text-gold-300 md:inline-flex lg:text-sm">Contact us</Link>
            <span aria-hidden="true" className={cn('hidden h-5 w-px lg:block', homeOverlay ? 'bg-white/50' : 'bg-forest-800/35')} />
            <Link to="/book" className="inline-flex h-10 items-center justify-center border border-[#b19a79] bg-[#8e7958] px-3 text-[10px] font-semibold uppercase tracking-[0.08em] text-white transition-colors hover:bg-[#786443] sm:h-12 sm:px-6 sm:text-xs">
              Reserve
            </Link>
          </div>
        </div>
        {open && <nav id="site-menu" aria-label="Site menu" className={cn('absolute inset-x-0 top-full max-h-[calc(100vh-5rem)] overflow-y-auto border-t shadow-xl sm:max-h-[calc(100vh-6rem)]', homeOverlay ? 'border-white/15 bg-forest-900/95 text-white backdrop-blur-xl' : 'border-sand bg-ivory text-forest-800')}>
          <div className="mx-auto grid max-w-7xl grid-cols-2 gap-1 px-4 py-4 sm:px-7 md:grid-cols-3 lg:grid-cols-4">
            {[...PRIMARY_NAV, ...DISCOVER_NAV].map(([to, label]) => <NavLink key={to} to={to} end={to === '/'} onClick={() => setOpen(false)} className={({ isActive }) => cn(
              'block px-3 py-3 text-sm font-medium transition-colors',
              homeOverlay ? isActive ? 'text-gold-300' : 'text-white/90 hover:bg-white/10 hover:text-white' : isActive ? 'text-gold-600' : 'text-forest-800 hover:bg-sand hover:text-gold-600',
            )}>{label}</NavLink>)}
            <Link to="/booking/lookup" onClick={() => setOpen(false)} className={cn('block px-3 py-3 text-sm font-medium transition-colors', homeOverlay ? 'text-white/80 hover:bg-white/10 hover:text-white' : 'text-forest-800 hover:bg-sand hover:text-gold-600')}>Find my booking</Link>
            <Link to="/contact" onClick={() => setOpen(false)} className={cn('block px-3 py-3 text-sm font-medium transition-colors sm:hidden', homeOverlay ? 'text-white/80 hover:bg-white/10 hover:text-white' : 'text-forest-800 hover:bg-sand hover:text-gold-600')}>Contact us</Link>
          </div>
        </nav>}
      </header>
      <main id="main"><Outlet /></main>
      <footer className="bg-forest-900 text-white/80">
        <div className="mx-auto grid max-w-7xl gap-x-10 gap-y-10 px-4 py-12 sm:px-6 sm:grid-cols-2 md:grid-cols-5 md:gap-x-8 lg:gap-x-12">
          <div className="space-y-4 sm:col-span-2 md:col-span-2">
            <Brand light />
            <p className="max-w-md text-sm leading-relaxed">{footer?.content?.about ?? p?.description}</p>
            <div className="flex gap-2 pt-1">
              {s.facebook && <a aria-label="Facebook" href={s.facebook} target="_blank" rel="noreferrer noopener" className="grid h-9 w-9 place-items-center rounded-full border border-white/15 transition-colors hover:border-[#e7d7ac] hover:bg-white/10 hover:text-[#e7d7ac]"><Facebook className="h-4 w-4" /></a>}
              {s.instagram && <a aria-label="Instagram" href={s.instagram} target="_blank" rel="noreferrer noopener" className="grid h-9 w-9 place-items-center rounded-full border border-white/15 transition-colors hover:border-[#e7d7ac] hover:bg-white/10 hover:text-[#e7d7ac]"><Instagram className="h-4 w-4" /></a>}
              {s.youtube && <a aria-label="YouTube" href={s.youtube} target="_blank" rel="noreferrer noopener" className="grid h-9 w-9 place-items-center rounded-full border border-white/15 transition-colors hover:border-[#e7d7ac] hover:bg-white/10 hover:text-[#e7d7ac]"><Youtube className="h-4 w-4" /></a>}
              {s.whatsapp && <a aria-label="WhatsApp" href={s.whatsapp} target="_blank" rel="noreferrer noopener" className="grid h-9 w-9 place-items-center rounded-full border border-white/15 transition-colors hover:border-[#e7d7ac] hover:bg-white/10 hover:text-[#e7d7ac]"><MessageCircle className="h-4 w-4" /></a>}
            </div>
          </div>
          <div>
            <h3 className="mb-4 font-serif text-lg text-[#e7d7ac]">Explore</h3>
            <ul className="space-y-3 text-sm">
              {[['/rooms', 'Rooms'], ['/restaurant', 'Dining'], ['/events', 'Events'], ['/offers', 'Offers'], ['/faq', 'FAQs']].map(([to, label]) => <li key={to}><Link className="transition-colors hover:text-white" to={to}>{label}</Link></li>)}
            </ul>
          </div>
          <div>
            <h3 className="mb-4 font-serif text-lg text-[#e7d7ac]">Bookings</h3>
            <ul className="space-y-3 text-sm">
              <li><Link className="transition-colors hover:text-white" to="/booking/search">Book a room</Link></li>
              <li><Link className="transition-colors hover:text-white" to="/events/book">Book the event centre</Link></li>
              <li><Link className="transition-colors hover:text-white" to="/booking/lookup">Find my booking</Link></li>
            </ul>
          </div>
          <div>
            <h3 className="mb-4 font-serif text-lg text-[#e7d7ac]">Contact</h3>
            <ul className="space-y-3 text-sm">
              {(p?.address || p?.town) && <li className="flex items-start gap-2"><MapPin className="mt-0.5 h-4 w-4 shrink-0 text-[#e7d7ac]" /><span>{[p.address, p.town, p.region].filter(Boolean).join(', ')}</span></li>}
              {p?.phones?.map((x: string) => <li key={x} className="flex items-center gap-2"><Phone className="h-4 w-4 shrink-0 text-[#e7d7ac]" /><a className="transition-colors hover:text-white" href={`tel:${x}`}>{x}</a></li>)}
              {p?.emails?.map((x: string) => <li key={x} className="flex items-center gap-2"><Mail className="h-4 w-4 shrink-0 text-[#e7d7ac]" /><a className="break-all transition-colors hover:text-white" href={`mailto:${x}`}>{x}</a></li>)}
              {!p?.phones?.length && !p?.emails?.length && <li className="text-white/50">Contact details coming soon</li>}
            </ul>
          </div>
        </div>
        <div className="border-t border-white/10 px-4 py-5 text-xs text-white/60">
          <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-3 sm:px-2 md:flex-row">
            <span className="text-center">{footer?.content?.copyright ?? `© ${new Date().getFullYear()} ${p?.name ?? ''}`}</span>
            <nav aria-label="Legal" className="flex flex-wrap justify-center gap-x-5 gap-y-2">
              <Link className="transition-colors hover:text-white" to="/privacy-policy">Privacy</Link>
              <Link className="transition-colors hover:text-white" to="/terms">Terms</Link>
              <Link className="transition-colors hover:text-white" to="/cancellation-policy">Cancellation</Link>
            </nav>
          </div>
        </div>
      </footer>
    </div>
  )
}
