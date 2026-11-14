/** Recognize both the public API apply link and the canonical generic flow path. */
export function genericPostingId(pathname: string, search: string): number | null {
  const route = /^\/apply\/programs\/([1-9]\d*)(?:\/.*)?$/.exec(pathname)
  const raw = route?.[1] ?? (pathname.startsWith('/apply') ? new URLSearchParams(search).get('posting') : null)
  if (!raw || !/^[1-9]\d*$/.test(raw)) return null
  const id = Number(raw)
  return Number.isSafeInteger(id) ? id : null
}
