import { cn } from '@/lib/utils'

export type MediaObj = { id: string; url: string; variants?: { sm?: string; md?: string; lg?: string }; alt?: string; width?: number; height?: number } | null | undefined

/** Responsive, lazy image. Missing media is omitted rather than replaced with a placeholder. */
export function Img({ media, className, sizes = '(min-width: 1024px) 50vw, 100vw', eager, label }: { media: MediaObj; className?: string; sizes?: string; eager?: boolean; label?: string }) {
  if (!media) return null
  const v = media.variants
  return (
    <img
      src={v?.md ?? media.url}
      srcSet={v ? `${v.sm} 480w, ${v.md} 960w, ${v.lg} 1600w` : undefined}
      sizes={sizes}
      alt={media.alt ?? label ?? ''}
      width={media.width}
      height={media.height}
      loading={eager ? 'eager' : 'lazy'}
      decoding="async"
      className={cn('object-cover', className)}
    />
  )
}
