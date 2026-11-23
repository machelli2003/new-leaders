import { Helmet } from 'react-helmet-async'
import { useSite } from '@/public/data'

export function Seo({ title, description, path, noindex }: { title?: string; description?: string; path?: string; noindex?: boolean }) {
  const { data } = useSite()
  const name = data?.profile?.name ?? 'New Leaders Hotel'
  const full = title ? `${title} | ${name}` : `${name} – ${data?.profile?.town ?? 'Akyem Tafo'}`
  const desc = description ?? data?.profile?.description ?? `${name}, ${data?.profile?.town ?? ''} ${data?.profile?.region ?? ''}`.trim()
  const url = path ? `${window.location.origin}${path}` : undefined
  return (
    <Helmet>
      <title>{full}</title>
      <meta name="description" content={desc.slice(0, 300)} />
      <meta property="og:title" content={full} />
      <meta property="og:description" content={desc.slice(0, 300)} />
      <meta property="og:type" content="website" />
      {url && <link rel="canonical" href={url} />}
      {url && <meta property="og:url" content={url} />}
      {noindex && <meta name="robots" content="noindex,nofollow" />}
    </Helmet>
  )
}
