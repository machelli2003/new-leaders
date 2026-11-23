import { useRef, useState } from 'react'
import { ImagePlus, X } from 'lucide-react'
import { toast } from 'sonner'
import { api, errMsg } from '@/lib/api'
import { useGet } from '@/lib/hooks'
import { useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/form'
import { Modal } from '@/components/ui/ui'
import { Img } from '@/components/Img'

/** Picks one or many images from the media library (or uploads new ones). Value = media ids. */
export function MediaPicker({ value, onChange, multiple, category = 'other', label }: { value: string[] | string | null | undefined; onChange: (v: any) => void; multiple?: boolean; category?: string; label?: string }) {
  const ids: string[] = Array.isArray(value) ? value : value ? [value] : []
  const [open, setOpen] = useState(false); const [q, setQ] = useState(''); const [busy, setBusy] = useState(false)
  const file = useRef<HTMLInputElement>(null); const qc = useQueryClient()
  const lib = useGet(['media-pick'], '/media', { q, page_size: 60 }, open)
  const all = useGet(['media-all'], '/media', { page_size: 200 })
  const byId = new Map<string, any>((all.data?.items ?? []).map((m: any) => [m.id, m]))
  const toggle = (id: string) => { if (multiple) onChange(ids.includes(id) ? ids.filter((i) => i !== id) : [...ids, id]); else { onChange(id); setOpen(false) } }
  const upload = async (files: FileList | null) => {
    if (!files?.length) return
    setBusy(true)
    try {
      const fd = new FormData(); Array.from(files).forEach((f) => fd.append('files', f)); fd.append('category', category)
      const res = await api<any[]>('/media', { form: fd })
      qc.invalidateQueries({ queryKey: ['media-pick'] }); qc.invalidateQueries({ queryKey: ['media-all'] })
      if (!multiple) { onChange(res[0].id); setOpen(false) } else onChange([...ids, ...res.map((r) => r.id)])
      toast.success('Uploaded')
    } catch (e) { toast.error(errMsg(e)) } finally { setBusy(false) }
  }
  return (<div className="space-y-2">{label && <div className="text-sm font-medium">{label}</div>}
    <div className="flex flex-wrap gap-2">{ids.map((id) => <div key={id} className="relative"><Img media={byId.get(id) ?? null} className="h-20 w-28 rounded-md" label="" />
      <button type="button" aria-label="Remove image" className="absolute -right-1 -top-1 rounded-full bg-red-600 p-0.5 text-white" onClick={() => onChange(multiple ? ids.filter((i) => i !== id) : null)}><X className="h-3 w-3" /></button></div>)}
      {(multiple || !ids.length) && <button type="button" onClick={() => setOpen(true)} className="grid h-20 w-28 place-items-center rounded-md border border-dashed border-[var(--border)] text-xs text-[var(--muted)] hover:bg-[var(--soft)]"><span className="flex flex-col items-center"><ImagePlus className="h-5 w-5" />{multiple ? 'Add images' : 'Choose image'}</span></button>}</div>
    <Modal open={open} onOpenChange={setOpen} title="Media library" wide><div className="space-y-3">
      <div className="flex gap-2"><Input placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} /><input ref={file} type="file" hidden multiple accept="image/jpeg,image/png,image/webp" onChange={(e) => upload(e.target.files)} /><Button type="button" loading={busy} onClick={() => file.current?.click()}>Upload</Button></div>
      <div className="grid max-h-96 grid-cols-3 gap-2 overflow-auto sm:grid-cols-4">{(lib.data?.items ?? []).map((m: any) => <button type="button" key={m.id} onClick={() => toggle(m.id)} className={`overflow-hidden rounded-md border-2 ${ids.includes(m.id) ? 'border-[var(--primary)]' : 'border-transparent'}`}><Img media={m} className="h-24 w-full" sizes="160px" /></button>)}
        {lib.data && !lib.data.items.length && <p className="col-span-full py-8 text-center text-sm text-[var(--muted)]">No images yet. Upload JPEG, PNG or WEBP files.</p>}</div>
      {multiple && <Button type="button" onClick={() => setOpen(false)}>Done</Button>}</div></Modal></div>)
}
