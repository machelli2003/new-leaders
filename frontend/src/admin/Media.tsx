import { useRef, useState } from 'react'
import { toast } from 'sonner'
import { Upload } from 'lucide-react'
import { api, errMsg } from '@/lib/api'
import { useAct, useGet } from '@/lib/hooks'
import { useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Field, Input, Select, Textarea } from '@/components/ui/form'
import { Confirm, Modal, PageHeader, QueryState } from '@/components/ui/ui'
import { Img } from '@/components/Img'

const CATS = ['logo', 'banner', 'room', 'facility', 'restaurant', 'event', 'gallery', 'promotion', 'other']

export function MediaLibrary() {
  const [q, setQ] = useState(''); const [cat, setCat] = useState(''); const [page, setPage] = useState(1)
  const [upCat, setUpCat] = useState('gallery'); const [sel, setSel] = useState<any>(null); const [del, setDel] = useState<any>(null); const [drag, setDrag] = useState(false)
  const [busy, setBusy] = useState(false); const [usage, setUsage] = useState<any[] | null>(null)
  const file = useRef<HTMLInputElement>(null); const rep = useRef<HTMLInputElement>(null); const qc = useQueryClient()
  const list = useGet(['media'], '/media', { q, category: cat, page, page_size: 36 })
  const refresh = () => qc.invalidateQueries({ queryKey: ['media'] })
  const upload = async (files: FileList | File[] | null) => {
    if (!files || !files.length) return
    setBusy(true)
    try { const fd = new FormData(); Array.from(files).forEach((f) => fd.append('files', f)); fd.append('category', upCat); await api('/media', { form: fd }); toast.success('Uploaded'); refresh() }
    catch (e) { toast.error(errMsg(e)) } finally { setBusy(false) }
  }
  const save = useAct(() => api(`/media/${sel.id}`, { method: 'PATCH', body: { title: sel.title, alt_text: sel.alt_text, description: sel.description, category: sel.category, status: sel.status } }), { ok: 'Saved', invalidate: [['media']], onOk: () => setSel(null) })
  const remove = useAct((force: boolean) => api(`/media/${del.id}`, { method: 'DELETE', query: force ? { force: true } : undefined }), { ok: 'Deleted', invalidate: [['media']], onOk: () => { setDel(null); setSel(null); setUsage(null) } })
  const replace = async (f?: File) => {
    if (!f) return
    try { const fd = new FormData(); fd.append('file', f); await api(`/media/${sel.id}/replace`, { form: fd }); toast.success('Replaced everywhere this image is used'); refresh(); setSel(null) } catch (e) { toast.error(errMsg(e)) }
  }
  const askDelete = async (m: any) => { setDel(m); try { setUsage(await api(`/media/${m.id}/usage`)) } catch { setUsage([]) } }
  return (<><PageHeader title="Media library" desc="JPEG, PNG or WEBP. Optimised sizes are generated automatically. SVG and other types are rejected." />
    <div onDragOver={(e) => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)} onDrop={(e) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files) }}
      className={`mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border-2 border-dashed p-6 ${drag ? 'border-[var(--primary)] bg-[var(--soft)]' : 'border-[var(--border)]'}`}>
      <div className="flex items-center gap-3 text-sm"><Upload className="h-6 w-6 text-[var(--muted)]" />Drag and drop images here, or choose files</div>
      <div className="flex gap-2"><Select aria-label="Upload category" className="w-36" value={upCat} onChange={(e) => setUpCat(e.target.value)}>{CATS.map((c) => <option key={c}>{c}</option>)}</Select>
        <input ref={file} hidden type="file" multiple accept="image/jpeg,image/png,image/webp" onChange={(e) => upload(e.target.files)} /><Button loading={busy} onClick={() => file.current?.click()}>Choose files</Button></div></div>
    <div className="mb-4 flex gap-2"><Input placeholder="Search title or description" value={q} onChange={(e) => { setQ(e.target.value); setPage(1) }} className="max-w-xs" /><Select aria-label="Category" className="w-40" value={cat} onChange={(e) => { setCat(e.target.value); setPage(1) }}><option value="">All categories</option>{CATS.map((c) => <option key={c}>{c}</option>)}</Select></div>
    <QueryState q={list} empty={{ show: list.data?.items.length === 0, text: 'No images yet. Upload the hotel’s real photos.' } as any}>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">{list.data?.items.map((m: any) => <button key={m.id} onClick={() => setSel({ ...m })} className="group overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--card)] text-left"><Img media={m} className="h-28 w-full" sizes="200px" /><div className="p-2 text-xs"><div className="truncate font-medium">{m.title}</div><div className="text-[var(--muted)]">{m.category} · {m.status}</div></div></button>)}</div>
      {list.data && list.data.total > 36 && <div className="mt-4 flex justify-center gap-2"><Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</Button><Button variant="outline" size="sm" disabled={page * 36 >= list.data.total} onClick={() => setPage(page + 1)}>Next</Button></div>}</QueryState>
    <Modal open={!!sel} onOpenChange={() => setSel(null)} title="Image details">{sel && <div className="space-y-3">
      <Img media={sel} className="h-48 w-full rounded-lg" />
      <Field label="Title"><Input value={sel.title ?? ''} onChange={(e) => setSel({ ...sel, title: e.target.value })} /></Field>
      <Field label="Alt text" hint="Describes the image for screen readers and search"><Input value={sel.alt_text ?? ''} onChange={(e) => setSel({ ...sel, alt_text: e.target.value })} /></Field>
      <Field label="Description"><Textarea value={sel.description ?? ''} onChange={(e) => setSel({ ...sel, description: e.target.value })} /></Field>
      <div className="grid grid-cols-2 gap-3"><Field label="Category"><Select value={sel.category} onChange={(e) => setSel({ ...sel, category: e.target.value })}>{CATS.map((c) => <option key={c}>{c}</option>)}</Select></Field><Field label="Status"><Select value={sel.status} onChange={(e) => setSel({ ...sel, status: e.target.value })}><option value="published">Published</option><option value="draft">Draft</option></Select></Field></div>
      <div className="flex flex-wrap gap-2"><Button loading={save.isPending} onClick={() => save.mutate(undefined)}>Save</Button><input ref={rep} hidden type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => replace(e.target.files?.[0])} /><Button variant="outline" onClick={() => rep.current?.click()}>Replace file</Button><Button variant="destructive" onClick={() => askDelete(sel)}>Delete</Button></div></div>}</Modal>
    <Confirm open={!!del} onOpenChange={() => { setDel(null); setUsage(null) }} danger title="Delete image?" confirmLabel={usage?.length ? 'Delete anyway' : 'Delete'} loading={remove.isPending}
      desc={usage?.length ? `This image is used in: ${usage.map((u) => u.name || u.type).join(', ')}. Deleting leaves blank images there.` : 'This cannot be undone.'} onConfirm={() => remove.mutate(!!usage?.length)} /></>)
}
