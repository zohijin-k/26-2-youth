/** Officer requests return to their original route after a session expires. */
export function officerSessionResponse(path: string, response: Pick<Response, 'status'>): void {
  if (typeof window === 'undefined' || !path.startsWith('/api/officer/') || path.endsWith('/login')) return
  if (response.status === 401) window.dispatchEvent(new Event('officer-session-expired'))
}

export function officerReturnPath(value: string | null): string {
  return value && /^\/officer(?:\/|\?|$)/.test(value) && !value.startsWith('/officer/login') ? value : '/officer'
}

export function officerLoginUrl(path: string): string {
  return `/officer/login?returnTo=${encodeURIComponent(officerReturnPath(path))}`
}
