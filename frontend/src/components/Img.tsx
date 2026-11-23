import { ImageOff } from 'lucide-react'
import { cn } from '@/lib/utils'

export type MediaObj = { id: string; url: string; variants?: { sm?: string; md?: string; lg?: string }; alt?: string; width?: number; height?: number } | null | undefined

/** Responsive, lazy image. With no image, shows a clearly-labelled PLACEHOLDER (never a fake photo). */
export function Img({ media, className, sizes = '(min-width: 1024px) 50vw, 100vw', eager, label }: { media: MediaObj; className?: string; sizes?: string; eager?: boolean; label?: string }) {
  if (!media) {
    return (
      <div className={cn('flex flex-col items-center justify-center gap-1 bg-gradient-to-br from-forest-50 to-sand text-center text-forest-700/70', className)} role="img" aria-label="Photo placeholder">
        <ImageOff className="h-6 w-6" />
        <span className="px-2 text-[11px] font-medium uppercase tracking-wider">Photo placeholder{label ? ` · ${label}` : ''}</span>
        <span className="px-2 text-[10px]">Upload in Media Library</span>
      </div>
    )
  }
  const v = media.variants
  return (
    <img
      src={v?.md ?? media.url}
      srcSet={v ? `${v.sm} 480w, ${v.md} 960w, ${v.lg} 1600w` : undefined}
      sizes={sizes}
      alt={media.alt ?? ''}
      width={media.width}
      height={media.height}
      loading={eager ? 'eager' : 'lazy'}
      decoding="async"
      className={cn('object-cover', className)}
    />
  )
}
