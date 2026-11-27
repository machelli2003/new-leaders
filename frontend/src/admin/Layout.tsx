import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Bell, BedDouble, BookOpen, CalendarDays, ChevronLeft, ClipboardList, CreditCard, DoorOpen, FileBarChart, Globe, Hammer, Image, LayoutDashboard, LogOut, Menu, Moon, Receipt, Search, Settings, Sparkles, Sun, Tag, Users, UserCog, ScrollText, Wand2, Wrench } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/lib/auth'
import { api } from '@/lib/api'
import { useGet, useAct } from '@/lib/hooks'
import { Seo } from '@/components/Seo'
import { fmtDateTime } from '@/lib/utils'

const NAV: { to: string; label: string; icon: any; perm: string; group: string }[] = [
  { to: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, perm: 'dashboard.view', group: 'Overview' },
  { to: 'reservations', label: 'Reservations', icon: BookOpen, perm: 'reservations.view', group: 'Front desk' },
  { to: 'calendar', label: 'Availability', icon: CalendarDays, perm: 'availability.view', group: 'Front desk' },
  { to: 'front-desk', label: 'Check-in / out', icon: DoorOpen, perm: 'checkin.manage', group: 'Front desk' },
  { to: 'guests', label: 'Guests', icon: Users, perm: 'guests.view', group: 'Front desk' },
  { to: 'rooms', label: 'Rooms & categories', icon: BedDouble, perm: 'rooms.view', group: 'Hotel' },
  { to: 'event-venues', label: 'Event venues', icon: CalendarDays, perm: 'rooms.view', group: 'Events' },
  { to: 'event-bookings', label: 'Event bookings', icon: ClipboardList, perm: 'reservations.view', group: 'Events' },
  { to: 'housekeeping', label: 'Housekeeping', icon: Sparkles, perm: 'housekeeping.view', group: 'Hotel' },
  { to: 'maintenance', label: 'Maintenance', icon: Wrench, perm: 'maintenance.manage', group: 'Hotel' },
  { to: 'payments', label: 'Payments', icon: CreditCard, perm: 'payments.view', group: 'Finance' },
  { to: 'refunds', label: 'Refunds', icon: Receipt, perm: 'refunds.view', group: 'Finance' },
  { to: 'pricing', label: 'Pricing & offers', icon: Tag, perm: 'pricing.manage', group: 'Finance' },
  { to: 'reports', label: 'Reports', icon: FileBarChart, perm: 'reports.operational', group: 'Finance' },
  { to: 'website', label: 'Website content', icon: Globe, perm: 'website.manage', group: 'Website' },
  { to: 'media', label: 'Media library', icon: Image, perm: 'media.manage', group: 'Website' },
  { to: 'staff', label: 'Staff', icon: UserCog, perm: 'staff.manage', group: 'Admin' },
  { to: 'audit-logs', label: 'Audit logs', icon: ScrollText, perm: 'audit.view', group: 'Admin' },
  { to: 'settings', label: 'Settings', icon: Settings, perm: 'hotel.manage', group: 'Admin' },
]
const SUPER = [
  { to: 'dashboard', label: 'System overview', icon: LayoutDashboard }, { to: 'setup', label: 'Setup wizard', icon: Wand2 }, { to: 'logs', label: 'Activity logs', icon: ClipboardList },
]

function useTheme() {
  const [dark, setDark] = useState(() => localStorage.getItem('nlh_theme') === 'dark')
  useEffect(() => { document.documentElement.classList.toggle('dark', dark); try { localStorage.setItem('nlh_theme', dark ? 'dark' : 'light') } catch { /* */ } }, [dark])
  return [dark, setDark] as const
}

function Notifications() {
  const [open, setOpen] = useState(false)
  const q = useGet(['notifs'], '/notifications', { page_size: 15 })
  const read = useAct((id: string) => api(`/notifications/${id}/read`, { method: 'POST' }), { invalidate: [['notifs']] })
  const all = useAct(() => api('/notifications/read-all', { method: 'POST' }), { invalidate: [['notifs']] })
  const items: any[] = q.data?.items ?? []
  const unread = items.filter((n) => !n.read).length
  return (<div className="relative">
    <button aria-label="Notifications" className="relative rounded-md p-2 hover:bg-[var(--soft)]" onClick={() => setOpen(!open)}><Bell className="h-5 w-5" />{unread > 0 && <span className="absolute right-1 top-1 grid h-4 min-w-4 place-items-center rounded-full bg-red-600 px-1 text-[10px] text-white">{unread}</span>}</button>
    {open && <div className="absolute right-0 z-40 mt-2 w-80 rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-lg">
      <div className="flex items-center justify-between border-b border-[var(--border)] px-3 py-2 text-sm font-medium">Notifications<button className="text-xs text-[var(--primary)]" onClick={() => all.mutate(undefined)}>Mark all read</button></div>
      <ul className="max-h-80 divide-y divide-[var(--border)] overflow-auto">{items.length === 0 && <li className="p-4 text-center text-sm text-[var(--muted)]">Nothing new</li>}
        {items.map((n) => <li key={n.id} className={`p-3 text-sm ${n.read ? 'opacity-60' : ''}`} onClick={() => !n.read && read.mutate(n.id)}><div className="font-medium">{n.title}</div><div className="text-xs text-[var(--muted)]">{n.body}</div><div className="mt-1 text-[10px] text-[var(--muted)]">{fmtDateTime(n.created_at)}</div></li>)}</ul></div>}</div>)
}

export function AdminLayout({ superAdmin }: { superAdmin?: boolean }) {
  const { user, logout, can } = useAuth(); const nav = useNavigate(); const loc = useLocation(); const qc = useQueryClient()
  const [collapsed, setCollapsed] = useState(false); const [mobile, setMobile] = useState(false); const [dark, setDark] = useTheme()
  const [search, setSearch] = useState('')
  useEffect(() => setMobile(false), [loc.pathname])
  useEffect(() => { if (user?.role === 'super_admin' && !superAdmin) api('/system/support/enter-hotel-portal', { method: 'POST' }).catch(() => {}) }, [user, superAdmin])
  const base = superAdmin ? '/super-admin' : '/admin'
  const items = superAdmin ? SUPER.map((s) => ({ ...s, group: 'Platform' })) : NAV.filter((n) => can(n.perm))
  const groups = [...new Set(items.map((i) => i.group))]
  const crumb = loc.pathname.replace(base, '').split('/').filter(Boolean).map((s) => s.replace(/-/g, ' ')).join(' / ')
  const side = (<nav aria-label="Main" className="flex h-full flex-col gap-4 overflow-y-auto p-3">
    <Link to={base} className="flex items-center gap-2 px-2 py-1 text-lg font-semibold text-[var(--primary)]"><BedDouble className="h-6 w-6 shrink-0" />{!collapsed && <span className="truncate">New Leaders</span>}</Link>
    {groups.map((g) => <div key={g}>{!collapsed && <div className="mb-1 px-2 text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)]">{g}</div>}
      {items.filter((i) => i.group === g).map((i) => <NavLink key={i.to} to={`${base}/${i.to}`} title={i.label} className={({ isActive }) => `flex items-center gap-3 rounded-md px-2 py-2 text-sm ${isActive ? 'bg-[var(--primary)] text-white' : 'hover:bg-[var(--soft)]'}`}><i.icon className="h-4 w-4 shrink-0" />{!collapsed && i.label}</NavLink>)}</div>)}
    {!superAdmin && user?.role === 'super_admin' && <Link className="rounded-md border border-dashed border-[var(--border)] px-2 py-2 text-xs" to="/super-admin/dashboard">← Super Admin console</Link>}
  </nav>)
  return (<div className="flex min-h-screen bg-[var(--soft)] text-[var(--fg)]"><Seo title="Admin" noindex />
    <aside className={`no-print sticky top-0 hidden h-screen border-r border-[var(--border)] bg-[var(--card)] md:block ${collapsed ? 'w-16' : 'w-60'}`}>{side}</aside>
    {mobile && <div className="fixed inset-0 z-40 md:hidden"><div className="absolute inset-0 bg-black/40" onClick={() => setMobile(false)} /><aside className="relative h-full w-64 bg-[var(--card)]">{side}</aside></div>}
    <div className="flex min-w-0 flex-1 flex-col">
      {user?.role === 'super_admin' && !superAdmin && <div className="no-print bg-amber-100 px-4 py-1 text-center text-xs text-amber-900">You are viewing the hotel environment as Super Admin. Actions are audited.</div>}
      <header className="no-print sticky top-0 z-30 flex items-center gap-3 border-b border-[var(--border)] bg-[var(--card)] px-4 py-2">
        <button aria-label="Menu" className="md:hidden" onClick={() => setMobile(true)}><Menu className="h-5 w-5" /></button>
        <button aria-label="Collapse sidebar" className="hidden md:block" onClick={() => setCollapsed(!collapsed)}><ChevronLeft className={`h-5 w-5 transition ${collapsed ? 'rotate-180' : ''}`} /></button>
        <div className="hidden text-sm capitalize text-[var(--muted)] sm:block">{crumb || 'home'}</div>
        {!superAdmin && can('reservations.view') && <form className="ml-auto hidden max-w-xs flex-1 sm:block" onSubmit={(e) => { e.preventDefault(); nav(`/admin/reservations?q=${encodeURIComponent(search)}`) }}><div className="relative"><Search className="absolute left-2 top-2 h-4 w-4 text-[var(--muted)]" /><input aria-label="Search reservations" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search reference, guest, phone…" className="w-full rounded-md border border-[var(--border)] bg-transparent py-1.5 pl-8 pr-2 text-sm" /></div></form>}
        <div className="ml-auto flex items-center gap-1 sm:ml-0">
          <button aria-label="Toggle theme" className="rounded-md p-2 hover:bg-[var(--soft)]" onClick={() => setDark(!dark)}>{dark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}</button>
          {!superAdmin && <Notifications />}
          <div className="ml-2 hidden text-right text-xs leading-tight sm:block"><div className="font-medium">{user?.name}</div><div className="text-[var(--muted)]">{user?.role_label}</div></div>
          <Link to="/admin/change-password" className="rounded-md px-2 py-1 text-xs hover:bg-[var(--soft)]">Password</Link>
          <button aria-label="Sign out" className="rounded-md p-2 hover:bg-[var(--soft)]" onClick={async () => { await logout(); qc.clear(); nav(superAdmin ? '/super-admin/login' : '/admin/login') }}><LogOut className="h-5 w-5" /></button></div>
      </header>
      <main id="main" className="min-w-0 flex-1 p-4 md:p-6"><Outlet /></main></div></div>)
}
