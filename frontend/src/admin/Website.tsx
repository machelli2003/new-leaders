import { useEffect, useState } from 'react'
import { ExternalLink, Plus, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import { useAct, useGet } from '@/lib/hooks'
import { SECTIONS, type FieldDef } from '@/lib/sections'
import { Button } from '@/components/ui/button'
import { Check, Field, Input, Select, Textarea } from '@/components/ui/form'
import { Badge, Card, CardBody, CardHeader, Modal, PageHeader, QueryState, StatusBadge, Table, Td, Th } from '@/components/ui/ui'
import { MediaPicker } from '@/components/MediaPicker'
import { fromMinor, toMinor } from '@/lib/utils'

function FieldEditor({ f, value, onChange }: { f: FieldDef; value: any; onChange: (v: any) => void }) {
  if (f.type === 'text') return <Field label={f.label} hint={f.hint}><Input value={value ?? ''} onChange={(e) => onChange(e.target.value)} /></Field>
  if (f.type === 'textarea') return <Field label={f.label} hint={f.hint}><Textarea rows={5} value={value ?? ''} onChange={(e) => onChange(e.target.value)} /></Field>
  if (f.type === 'money') return <Field label={f.label}><Input type="number" step="0.01" value={value == null ? '' : fromMinor(value)} onChange={(e) => onChange(e.target.value === '' ? null : toMinor(e.target.value))} /></Field>
  if (f.type === 'media') return <MediaPicker label={f.label} value={value} onChange={onChange} />
  if (f.type === 'medias') return <MediaPicker label={f.label} multiple value={value ?? []} onChange={onChange} />
  const list: any[] = value ?? []
  return (<div className="space-y-2"><div className="text-sm font-medium">{f.label}</div>
    {list.map((it, i) => <div key={i} className="relative space-y-2 rounded-lg border border-[var(--border)] p-3"><button type="button" aria-label="Remove" className="absolute right-2 top-2 text-red-600" onClick={() => onChange(list.filter((_, j) => j !== i))}><Trash2 className="h-4 w-4" /></button>
      {f.fields!.map((sf) => <FieldEditor key={sf.name} f={sf} value={it[sf.name]} onChange={(v) => onChange(list.map((x, j) => (j === i ? { ...x, [sf.name]: v } : x)))} />)}</div>)}
    <Button type="button" size="sm" variant="outline" onClick={() => onChange([...list, {}])}><Plus className="h-4 w-4" />Add</Button></div>)
}

function SectionEditor({ def, rec }: { def: (typeof SECTIONS)[number]; rec: any }) {
  const [c, setC] = useState<any>(rec?.draft ?? rec?.published ?? {})
  useEffect(() => setC(rec?.draft ?? rec?.published ?? {}), [def.key, rec?.updated_at])
  const inv = [['sections']] as any
  const save = useAct(() => api(`/website/admin/sections/${def.key}`, { method: 'PUT', body: { title: def.label, content: c } }), { ok: 'Draft saved', invalidate: inv })
  const publish = useAct(async () => { await api(`/website/admin/sections/${def.key}`, { method: 'PUT', body: { title: def.label, content: c } }); return api(`/website/admin/sections/${def.key}/publish`, { method: 'POST' }) }, { ok: 'Published', invalidate: inv })
  const unpub = useAct(() => api(`/website/admin/sections/${def.key}/unpublish`, { method: 'POST' }), { ok: 'Unpublished', invalidate: inv })
  return (<Card><CardHeader><div><h3 className="font-semibold">{def.label}</h3><div className="mt-1 flex gap-2"><StatusBadge status={rec?.status === 'missing' ? 'draft' : rec?.status} />{rec?.status === 'missing' && <span className="text-xs text-[var(--muted)]">Not written yet</span>}</div></div>
    <div className="flex flex-wrap gap-2"><Button size="sm" variant="outline" asChild><a href="/?preview=1" target="_blank" rel="noreferrer"><ExternalLink className="h-3 w-3" />Preview site</a></Button>{rec?.status === 'published' && <Button size="sm" variant="ghost" onClick={() => unpub.mutate(undefined)}>Unpublish</Button>}</div></CardHeader>
    <CardBody className="space-y-4">{def.fields.map((f) => <FieldEditor key={f.name} f={f} value={c[f.name]} onChange={(v) => setC({ ...c, [f.name]: v })} />)}
      <p className="text-xs text-[var(--muted)]">Write only real hotel information. Nothing is shown publicly until you publish. Use “Preview site” (staff only) to see drafts.</p>
      <div className="flex gap-2"><Button variant="outline" loading={save.isPending} onClick={() => save.mutate(undefined)}>Save draft</Button><Button loading={publish.isPending} onClick={() => publish.mutate(undefined)}>Save & publish</Button></div></CardBody></Card>)
}

const TYPES = [['facility', 'Facilities'], ['faq', 'FAQs'], ['event', 'Event types'], ['testimonial', 'Testimonials']]
function Items() {
  const [t, setT] = useState('facility'); const q = useGet(['items'], '/website/admin/items', { type: t }); const [e, setE] = useState<any>(null)
  const save = useAct(() => { const b = { type: t, title: e.title ?? '', body: e.body ?? '', question: e.question ?? '', answer: e.answer ?? '', icon: e.icon ?? '', author: e.author ?? '', media_id: e.media_id ?? null, media_ids: e.media_ids ?? [], status: e.status ?? 'draft', order: Number(e.order) || 0, verified: !!e.verified }; return e.id ? api(`/website/admin/items/${e.id}`, { method: 'PATCH', body: b }) : api('/website/admin/items', { body: b }) }, { ok: 'Saved', invalidate: [['items']], onOk: () => setE(null) })
  const del = useAct((id: string) => api(`/website/admin/items/${id}`, { method: 'DELETE' }), { ok: 'Deleted', invalidate: [['items']] })
  return (<div className="space-y-3"><div className="flex flex-wrap items-center gap-2">{TYPES.map(([k, l]) => <Button key={k} size="sm" variant={t === k ? 'default' : 'outline'} onClick={() => setT(k)}>{l}</Button>)}<Button size="sm" className="ml-auto" onClick={() => setE({ status: 'draft' })}><Plus className="h-4 w-4" />Add</Button></div>
    <QueryState q={q} empty={{ show: q.data?.length === 0, text: 'Nothing here yet.' } as any}><Table><thead><tr><Th>{t === 'faq' ? 'Question' : 'Title'}</Th><Th>Order</Th><Th>Status</Th><Th /></tr></thead><tbody>{q.data?.map((i: any) => <tr key={i.id}><Td>{i.question || i.title || i.author}{t === 'testimonial' && !i.verified && <Badge tone="amber" className="ml-2">Unverified</Badge>}</Td><Td>{i.order}</Td><Td><StatusBadge status={i.status} /></Td><Td className="space-x-1"><Button size="sm" variant="outline" onClick={() => setE(i)}>Edit</Button><Button size="sm" variant="ghost" onClick={() => del.mutate(i.id)}>Delete</Button></Td></tr>)}</tbody></Table></QueryState>
    <Modal wide open={!!e} onOpenChange={() => setE(null)} title={e?.id ? 'Edit' : 'Add'}>{e && <div className="space-y-3">
      {t === 'faq' ? <><Field label="Question"><Input value={e.question ?? ''} onChange={(x) => setE({ ...e, question: x.target.value })} /></Field><Field label="Answer"><Textarea value={e.answer ?? ''} onChange={(x) => setE({ ...e, answer: x.target.value })} /></Field></>
        : <><Field label={t === 'testimonial' ? 'Headline (optional)' : 'Title'}><Input value={e.title ?? ''} onChange={(x) => setE({ ...e, title: x.target.value })} /></Field><Field label={t === 'testimonial' ? 'Testimonial text' : 'Description'}><Textarea value={e.body ?? ''} onChange={(x) => setE({ ...e, body: x.target.value })} /></Field></>}
      {t === 'testimonial' && <><Field label="Guest name"><Input value={e.author ?? ''} onChange={(x) => setE({ ...e, author: x.target.value })} /></Field><Check label="Verified: this is a real testimonial supplied by the guest" checked={!!e.verified} onChange={(x) => setE({ ...e, verified: x.target.checked })} /></>}
      {t === 'facility' && <Field label="Icon name (lucide)" hint="e.g. wifi, car, utensils"><Input value={e.icon ?? ''} onChange={(x) => setE({ ...e, icon: x.target.value })} /></Field>}
      {t !== 'faq' && t !== 'testimonial' && <MediaPicker label="Image" category={t === 'event' ? 'event' : 'facility'} value={e.media_id} onChange={(v: string | null) => setE({ ...e, media_id: v })} />}
      <div className="grid grid-cols-2 gap-3"><Field label="Order"><Input type="number" value={e.order ?? 0} onChange={(x) => setE({ ...e, order: x.target.value })} /></Field><Field label="Status"><Select value={e.status} onChange={(x) => setE({ ...e, status: x.target.value })}><option value="draft">Draft</option><option value="published">Published</option><option value="archived">Archived</option></Select></Field></div>
      <Button loading={save.isPending} onClick={() => save.mutate(undefined)}>Save</Button></div>}</Modal></div>)
}

export function Website() {
  const q = useGet(['sections'], '/website/admin/sections'); const [tab, setTab] = useState('home.hero')
  const groups = [...new Set(SECTIONS.map((s) => s.group))]
  const def = SECTIONS.find((s) => s.key === tab)
  return (<><PageHeader title="Website content" desc="Edit sections as drafts, preview, then publish. The gallery automatically includes all published images from the Media Library." />
    <div className="grid gap-4 lg:grid-cols-4"><nav className="space-y-3 lg:col-span-1">{groups.map((g) => <div key={g}><div className="mb-1 text-[10px] font-semibold uppercase text-[var(--muted)]">{g}</div>{SECTIONS.filter((s) => s.group === g).map((s) => <button key={s.key} onClick={() => setTab(s.key)} className={`block w-full rounded-md px-2 py-1.5 text-left text-sm ${tab === s.key ? 'bg-[var(--primary)] text-white' : 'hover:bg-[var(--soft)]'}`}>{s.label}</button>)}</div>)}
      <div><div className="mb-1 text-[10px] font-semibold uppercase text-[var(--muted)]">Lists</div><button onClick={() => setTab('items')} className={`block w-full rounded-md px-2 py-1.5 text-left text-sm ${tab === 'items' ? 'bg-[var(--primary)] text-white' : 'hover:bg-[var(--soft)]'}`}>Facilities, FAQs, events, testimonials</button></div></nav>
      <div className="lg:col-span-3">{tab === 'items' ? <Items /> : <QueryState q={q}>{def && <SectionEditor def={def} rec={q.data?.find((s: any) => s.key === def.key)} />}</QueryState>}</div></div></>)
}
