import { useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight, Pause, Play } from 'lucide-react'
import { Img } from '@/components/Img'

export function GallerySlideshow({
  images,
  onOpen,
  intervalMs = 4000,
}: {
  images: any[]
  onOpen?: (img: any) => void
  intervalMs?: number
}) {
  const [idx, setIdx] = useState(0)
  const [playing, setPlaying] = useState(true)

  useEffect(() => {
    if (!playing || images.length <= 1) return
    const id = setInterval(() => setIdx((i) => (i + 1) % images.length), intervalMs)
    return () => clearInterval(id)
  }, [playing, images.length, intervalMs])

  if (!images.length) return null
  const current = images[idx % images.length]
  const prev = () => setIdx((i) => (i - 1 + images.length) % images.length)
  const next = () => setIdx((i) => (i + 1) % images.length)

  return (
    <div className="space-y-4">
      {/* Main auto-advancing slideshow */}
      <div className="group relative overflow-hidden rounded-2xl bg-forest-900 shadow-lg">
        <div
          className="relative aspect-[16/9] max-h-[65vh] w-full cursor-pointer overflow-hidden"
          onClick={() => onOpen?.(current)}
        >
          {images.map((g, i) => (
            <div
              key={g.id}
              className={`absolute inset-0 transition-all duration-700 ease-out ${
                i === idx % images.length ? 'scale-100 opacity-100' : 'pointer-events-none scale-105 opacity-0'
              }`}
            >
              <Img media={g} eager={i === 0} className="h-full w-full object-cover" sizes="100vw" />
            </div>
          ))}
          <div className="pointer-events-none absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-black/70 to-transparent" />
          <div className="absolute bottom-4 left-5 right-16 text-white">
            {current?.title && <p className="text-lg font-medium">{current.title}</p>}
            <p className="text-xs text-white/75">
              {(idx % images.length) + 1} / {images.length} · Click image to enlarge
            </p>
          </div>
        </div>

        {images.length > 1 && (
          <>
            <button
              type="button"
              onClick={prev}
              aria-label="Previous photo"
              className="absolute left-3 top-1/2 -translate-y-1/2 rounded-full bg-black/45 p-2.5 text-white backdrop-blur-sm transition hover:bg-black/70"
            >
              <ChevronLeft className="h-5 w-5" />
            </button>
            <button
              type="button"
              onClick={next}
              aria-label="Next photo"
              className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full bg-black/45 p-2.5 text-white backdrop-blur-sm transition hover:bg-black/70"
            >
              <ChevronRight className="h-5 w-5" />
            </button>
            <button
              type="button"
              onClick={() => setPlaying((p) => !p)}
              aria-label={playing ? 'Pause slideshow' : 'Play slideshow'}
              className="absolute bottom-4 right-4 rounded-full bg-black/50 p-2 text-white backdrop-blur-sm transition hover:bg-black/75"
            >
              {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            </button>
          </>
        )}
      </div>

      {/* Dots */}
      {images.length > 1 && (
        <div className="flex flex-wrap justify-center gap-2">
          {images.map((g, i) => (
            <button
              key={g.id}
              type="button"
              onClick={() => setIdx(i)}
              aria-label={`Go to slide ${i + 1}`}
              className={`h-2 rounded-full transition-all duration-300 ${
                i === idx % images.length ? 'w-7 bg-gold-500' : 'w-2 bg-forest-800/25 hover:bg-forest-800/50'
              }`}
            />
          ))}
        </div>
      )}

      {/* Continuous moving filmstrip */}
      {images.length > 1 && (
        <div className="overflow-hidden rounded-xl py-2">
          <div className="animate-marquee gap-3">
            {[...images, ...images].map((g, i) => (
              <button
                key={`${g.id}-${i}`}
                type="button"
                onClick={() => setIdx(i % images.length)}
                className={`h-24 w-36 shrink-0 overflow-hidden rounded-lg border-2 transition-transform duration-300 hover:scale-105 ${
                  i % images.length === idx % images.length ? 'border-gold-500' : 'border-transparent opacity-80 hover:opacity-100'
                }`}
              >
                <Img media={g} className="h-full w-full object-cover" sizes="150px" />
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
