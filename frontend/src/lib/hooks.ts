import { useMutation, useQuery, useQueryClient, type QueryKey } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api, errMsg } from './api'

export const useGet = <T = any>(key: QueryKey, path: string, query?: Record<string, any>, enabled = true) =>
  useQuery<T>({ queryKey: [...key, query], queryFn: () => api<T>(path, { query }), enabled })

/** Mutation with toast + cache invalidation. */
export function useAct<TIn = any, TOut = any>(fn: (v: TIn) => Promise<TOut>, opts: { invalidate?: QueryKey[]; ok?: string; onOk?: (r: TOut) => void } = {}) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (r) => { opts.invalidate?.forEach((k) => qc.invalidateQueries({ queryKey: k })); if (opts.ok) toast.success(opts.ok); opts.onOk?.(r) },
    onError: (e) => toast.error(errMsg(e)),
  })
}

export function usePreview() {
  if (typeof window === 'undefined') return false
  const q = new URLSearchParams(window.location.search)
  if (q.get('preview') === '1') sessionStorage.setItem('nlh_preview', '1')
  if (q.get('preview') === '0') sessionStorage.removeItem('nlh_preview')
  return sessionStorage.getItem('nlh_preview') === '1'
}
