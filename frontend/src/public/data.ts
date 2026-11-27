import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { usePreview } from '@/lib/hooks'

export function usePub<T = any>(key: string, path: string, query: Record<string, any> = {}) {
  const preview = usePreview()
  return useQuery<T>({ queryKey: ['pub', key, query, preview], queryFn: () => api<T>(path, { query: { ...query, preview: preview ? 'true' : undefined } }), staleTime: 30_000 })
}
export const useSite = () => usePub('site', '/website/site')
export const useSection = (key: string) => usePub<{ content: any; status: string }>(`sec-${key}`, `/website/sections/${key}`)
export const useItems = (type: string) => usePub<any[]>(`items-${type}`, `/website/items/${type}`)
export const useRooms = (featured = false) => usePub<any[]>(`rooms-${featured}`, '/website/rooms', { featured: featured || undefined })
export const useRoom = (slug: string) => usePub<any>(`room-${slug}`, `/website/rooms/${slug}`)
export const useOffers = () => usePub<any[]>('offers', '/website/offers')
export const useGallery = () => usePub<any[]>('gallery', '/website/gallery')
export const useEventVenues = () => usePub<any[]>('event-venues', '/event-venues')
