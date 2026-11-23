import { useEffect, useState } from 'react'

/* Minimal hash router.
   Phase 2 needs only a handful of routes; a full routing library is added in
   Phase 4 when authentication introduces real navigation requirements.
   Hash routing means the app works on any static host without server config. */

/* Last route that was actually a route. Anchor hashes like `#how` or
   `#main-content` (skip link) must never be interpreted as routes. */
let lastValidPath = '/'

export function getHashPath(): string {
  const raw = window.location.hash.replace(/^#/, '')
  if (!raw.startsWith('/')) return lastValidPath
  lastValidPath = raw === '' ? '/' : raw
  return lastValidPath
}

export function navigate(path: string): void {
  const target = path.startsWith('#') ? path : `#${path.startsWith('/') ? path : `/${path}`}`
  if (window.location.hash === target) return
  window.location.hash = target
}

export function useRoute(): string {
  const [path, setPath] = useState<string>(getHashPath)

  useEffect(() => {
    const onChange = () => setPath(getHashPath())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])

  return path
}
