import { Link } from 'react-router-dom'
import { CheckCircle2, Circle } from 'lucide-react'
import { api } from '@/lib/api'
import { useAct, useGet } from '@/lib/hooks'
import { Button } from '@/components/ui/button'
import { Badge, Card, CardBody, CardHeader, PageHeader, QueryState, Stat } from '@/components/ui/ui'
import { fmtDateTime } from '@/lib/utils'

export function SuperDashboard() {
  const q = useGet(['sys'], '/system/overview'); const d = q.data
  const release = useAct(() => api<any>('/system/support/release-expired-holds', { method: 'POST' }), { ok: 'Expired holds released', invalidate: [['sys']] })
  return (<><PageHeader title="System overview" desc="Platform owner view. Hotel business data is available only through the hotel portal." actions={<><Button variant="outline" asChild><Link to="/admin/dashboard">Open hotel portal</Link></Button><Button variant="outline" loading={release.isPending} onClick={() => release.mutate(undefined)}>Release expired holds</Button></>} />
    <QueryState q={q}>{d && <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4"><Stat label="Environment" value={d.environment} /><Stat label="Paystack" value={d.integrations.paystack} sub="mode" /><Stat label="Email" value={d.integrations.email ? 'Configured' : 'Not configured'} tone={d.integrations.email ? undefined : 'warn'} /><Stat label="Storage" value={d.integrations.storage} />
        <Stat label="Rooms" value={d.counts.rooms} /><Stat label="Reservations" value={d.counts.reservations} /><Stat label="Staff" value={d.counts.staff} /><Stat label="Failed emails" value={d.failed_emails} tone={d.failed_emails ? 'warn' : undefined} /></div>
      <Card><CardHeader><h3 className="font-semibold">Setup progress</h3><Button size="sm" asChild><Link to="/super-admin/setup">Open setup wizard</Link></Button></CardHeader><CardBody className="text-sm">{d.setup.ready_to_publish ? 'All required steps complete.' : `${(d.setup.steps ?? []).filter((s: any) => s.complete).length} of ${(d.setup.steps ?? []).length} steps complete.`}</CardBody></Card>
      <Card><CardHeader><h3 className="font-semibold">Recent activity</h3></CardHeader><CardBody className="space-y-1 text-sm">{d.recent_audit.map((a: any) => <div key={a.id} className="flex justify-between"><span><span className="font-mono text-xs">{a.action}</span> · {a.actor_name ?? 'system'}</span><span className="text-[var(--muted)]">{fmtDateTime(a.created_at)}</span></div>)}</CardBody></Card></div>}</QueryState></>)
}

const LINKS: Record<string, string> = { profile: '/admin/settings', categories: '/admin/rooms', rooms: '/admin/rooms', pricing: '/admin/rooms', facilities: '/admin/website', website: '/admin/website', booking: '/admin/settings', payments: '/admin/settings', staff: '/admin/staff' }

export function Wizard() {
  const q = useGet(['setup'], '/hotel/setup-status'); const d = q.data
  const pub = useAct(() => api('/hotel/publish', { method: 'POST' }), { ok: 'Hotel is now live', invalidate: [['setup'], ['sys']] })
  const unpub = useAct(() => api('/hotel/unpublish', { method: 'POST' }), { ok: 'Site set to “coming soon”', invalidate: [['setup'], ['sys']] })
  return (<><PageHeader title="Setup wizard" desc="Complete each step with the hotel's real details. The public site shows “coming soon” until published." />
    <QueryState q={q}>{d && <div className="max-w-3xl space-y-3">
      {(d.steps ?? []).map((s: any, i: number) => <Card key={s.key ?? i}><CardBody className="flex items-start gap-3">{s.complete ? <CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-600" /> : <Circle className="mt-0.5 h-5 w-5 text-[var(--muted)]" />}
        <div className="flex-1"><div className="font-medium">{i + 1}. {s.label}{s.required === false && <Badge className="ml-2">Optional</Badge>}</div>{s.missing?.length > 0 && <div className="text-sm text-[var(--muted)]">{s.missing.join(' · ')}</div>}</div>{LINKS[s.key] && <Button size="sm" variant="outline" asChild><Link to={LINKS[s.key]}>{s.complete ? 'Review' : 'Complete'}</Link></Button>}</CardBody></Card>)}
      <Card><CardBody className="flex flex-wrap items-center justify-between gap-3"><div><div className="font-medium">{d.published ? 'The hotel website is live' : 'Website not published'}</div>{!d.published && !d.ready_to_publish && <div className="text-sm text-amber-700">Complete the required steps before publishing.</div>}</div>
        {d.published ? <Button variant="outline" loading={unpub.isPending} onClick={() => unpub.mutate(undefined)}>Unpublish</Button> : <Button disabled={!d.ready_to_publish} loading={pub.isPending} onClick={() => pub.mutate(undefined)}>Publish hotel</Button>}</CardBody></Card></div>}</QueryState></>)
}
