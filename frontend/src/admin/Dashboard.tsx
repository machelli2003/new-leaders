import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useAuth } from '@/lib/auth'
import { useGet } from '@/lib/hooks'
import { Card, CardBody, CardHeader, PageHeader, QueryState, Stat, StatusBadge } from '@/components/ui/ui'
import { fmtDate, money } from '@/lib/utils'

const Chart = ({ title, data, x, y, bar, money: m }: { title: string; data: any[]; x: string; y: string; bar?: boolean; money?: boolean }) => (
  <Card><CardHeader><h3 className="text-sm font-semibold">{title}</h3></CardHeader><CardBody className="h-64">
    {data?.length ? <ResponsiveContainer width="100%" height="100%">{bar
      ? <BarChart data={data}><CartesianGrid strokeDasharray="3 3" opacity={0.3} /><XAxis dataKey={x} fontSize={11} tickFormatter={(v) => String(v).slice(5)} /><YAxis fontSize={11} tickFormatter={(v) => (m ? String(v / 100) : v)} /><Tooltip formatter={(v: any) => (m ? money(v) : v)} /><Bar dataKey={y} fill="#2f5d46" radius={[3, 3, 0, 0]} /></BarChart>
      : <LineChart data={data}><CartesianGrid strokeDasharray="3 3" opacity={0.3} /><XAxis dataKey={x} fontSize={11} tickFormatter={(v) => String(v).slice(5)} /><YAxis fontSize={11} tickFormatter={(v) => (m ? String(v / 100) : v)} /><Tooltip formatter={(v: any) => (m ? money(v) : v)} /><Line dataKey={y} stroke="#b8923b" strokeWidth={2} dot={false} /></LineChart>}</ResponsiveContainer>
      : <p className="grid h-full place-items-center text-sm text-[var(--muted)]">No data in this period yet.</p>}</CardBody></Card>)

export function Dashboard() {
  const { can } = useAuth()
  const q = useGet(['dash'], '/reports/dashboard')
  const d = q.data
  return (<><PageHeader title="Dashboard" desc={d?.today ? `Today · ${fmtDate(d.today)} · Trends cover the last 30 days` : 'Today and recent operations'} />
    <QueryState q={q}>{d && <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Today's check-ins" value={d.todays_check_ins} /><Stat label="Today's check-outs" value={d.todays_check_outs} />
        <Stat label="Occupancy" value={`${d.occupancy_percent}%`} sub={`${d.rooms_occupied}/${d.rooms_total} rooms`} /><Stat label="Available rooms" value={d.rooms_available} />
        <Stat label="Pending reservations" value={d.pending_reservations} /><Stat label="Cancellation requests" value={d.cancellation_requests} />
        <Stat label="Needs attention" value={d.needs_attention} tone={d.needs_attention ? 'warn' : undefined} sub="Paid but no room, etc." /><Stat label="Rooms in maintenance" value={d.rooms_maintenance} />
        {d.total_revenue_minor !== undefined && <><Stat label="Revenue (net)" value={money(d.total_revenue_minor)} /><Stat label="Outstanding balances" value={money(d.outstanding_balances_minor)} /></>}</div>
      <div className="grid gap-4 xl:grid-cols-2">
        <Card><CardHeader><h3 className="text-sm font-semibold">Today's arrivals</h3></CardHeader><CardBody className="space-y-2 text-sm">
          {d.today_arrivals.length ? d.today_arrivals.map((item: any) => <Link key={item.id} to={`/admin/reservations/${item.id}`} className="flex items-center justify-between gap-3 rounded px-2 py-1 hover:bg-[var(--soft)]"><span>{item.reference} · {item.guest}<span className="ml-2 text-xs text-[var(--muted)]">{item.rooms} room(s)</span></span><StatusBadge status={item.status} /></Link>) : <p className="text-[var(--muted)]">No room arrivals today.</p>}
        </CardBody></Card>
        <Card><CardHeader><h3 className="text-sm font-semibold">Today's departures</h3></CardHeader><CardBody className="space-y-2 text-sm">
          {d.today_departures.length ? d.today_departures.map((item: any) => <Link key={item.id} to={`/admin/reservations/${item.id}`} className="flex items-center justify-between gap-3 rounded px-2 py-1 hover:bg-[var(--soft)]"><span>{item.reference} · {item.guest}<span className="ml-2 text-xs text-[var(--muted)]">{item.rooms} room(s)</span></span><StatusBadge status={item.status} /></Link>) : <p className="text-[var(--muted)]">No room departures today.</p>}
        </CardBody></Card>
        {can('housekeeping.view') && <Card><CardHeader><h3 className="text-sm font-semibold">Rooms not ready <span className="text-[var(--muted)]">({d.rooms_not_ready?.length ?? 0})</span></h3></CardHeader><CardBody className="space-y-2 text-sm">
          {d.rooms_not_ready?.length ? d.rooms_not_ready.map((room: any) => <Link key={room.id} to="/admin/housekeeping" className="flex justify-between rounded px-2 py-1 hover:bg-[var(--soft)]"><span>Room {room.number}</span><StatusBadge status={room.status} /></Link>) : <p className="text-[var(--muted)]">All rooms are ready.</p>}
        </CardBody></Card>}
        {can('payments.view') && <Card><CardHeader><h3 className="text-sm font-semibold">Overdue balances <span className="text-[var(--muted)]">({d.overdue_balance_count ?? 0})</span></h3></CardHeader><CardBody className="space-y-2 text-sm">
          {d.overdue_balances?.length ? d.overdue_balances.map((item: any) => <Link key={item.id} to={`/admin/reservations/${item.id}`} className="flex justify-between gap-3 rounded px-2 py-1 hover:bg-[var(--soft)]"><span>{item.reference} · {item.guest}</span><span className="text-amber-700">{money(item.balance_minor)}</span></Link>) : <p className="text-[var(--muted)]">No overdue balances.</p>}
        </CardBody></Card>}
        {can('maintenance.manage') && <Card><CardHeader><h3 className="text-sm font-semibold">Open maintenance <span className="text-[var(--muted)]">({d.open_maintenance_count ?? 0})</span></h3></CardHeader><CardBody className="space-y-2 text-sm">
          {d.open_maintenance?.length ? d.open_maintenance.map((item: any) => <Link key={item.id} to="/admin/maintenance" className="flex justify-between gap-3 rounded px-2 py-1 hover:bg-[var(--soft)]"><span>{item.title}<span className="ml-2 text-xs text-[var(--muted)]">{item.room_numbers?.join(', ')}</span></span><StatusBadge status={item.priority} /></Link>) : <p className="text-[var(--muted)]">No open maintenance requests.</p>}
        </CardBody></Card>}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {d.revenue_trend && <Chart title="Revenue (GHS)" data={d.revenue_trend} x="date" y="net_minor" bar money />}
        <Chart title="Occupancy %" data={d.occupancy_trend} x="date" y="occupancy_percent" />
        <Chart title="New reservations per day" data={d.reservation_trend} x="date" y="count" bar />
        {d.category_performance && <Chart title="Revenue by room category (GHS)" data={d.category_performance} x="category" y="revenue" bar />}</div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card><CardHeader><h3 className="text-sm font-semibold">Upcoming arrivals</h3></CardHeader><CardBody className="space-y-2 text-sm">{d.upcoming.length ? d.upcoming.map((u: any) => <Link key={u.id} to={`/admin/reservations/${u.id}`} className="flex justify-between rounded px-2 py-1 hover:bg-[var(--soft)]"><span>{u.reference} · {u.guest}</span><span className="text-[var(--muted)]">{fmtDate(u.check_in)}</span></Link>) : <p className="text-[var(--muted)]">No upcoming confirmed arrivals.</p>}</CardBody></Card>
        {can('payments.view') && d.recent_payments && <Card><CardHeader><h3 className="text-sm font-semibold">Recent payments</h3></CardHeader><CardBody className="space-y-2 text-sm">{d.recent_payments.length ? d.recent_payments.map((p: any) => <div key={p.id} className="flex items-center justify-between px-2 py-1"><span>{p.reservation ?? p.reference}</span><span className="flex items-center gap-2">{money(p.amount_minor)} <StatusBadge status={p.status} /></span></div>) : <p className="text-[var(--muted)]">No payments yet.</p>}</CardBody></Card>}</div>
    </div>}</QueryState></>)
}
