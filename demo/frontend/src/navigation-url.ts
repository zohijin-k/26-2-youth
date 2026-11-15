const NAVIGATION_PARAMS = [
  'mode', 'application', 'stage', 'previous', 'from',
  'o_role', 'o_region', 'o_town', 'o_program', 'o_status', 'o_ai_status',
  'o_submitted_from', 'o_submitted_to', 'o_sort', 'o_page', 'o_page_size',
  'o_open', 'o_slot', 'o_criteria', 'o_criteria_program',
  'role', 'region', 'town', 'program', 'status', 'ai', 'submitted_from',
  'submitted_to', 'sort', 'page', 'page_size', 'slot',
  'queue', 'q', 'posting',
] as const

export function currentParams(): URLSearchParams {
  return new URLSearchParams(window.location.search)
}

/** 어느 화면을 띄울지. 두 화면은 각자 주소 전체를 자기 것으로 다루므로 한 번에 하나만 마운트한다. */
export type Mode = 'applicant' | 'officer'

export function currentMode(): Mode {
  if (window.location.pathname.startsWith('/officer')) return 'officer'
  if (window.location.pathname.startsWith('/apply')) return 'applicant'
  return currentParams().get('mode') === 'officer' ? 'officer' : 'applicant'
}

function targetUrl(path: string, params: Record<string, string | null>): URL {
  const url = new URL(window.location.href)
  url.pathname = path
  for (const key of NAVIGATION_PARAMS) url.searchParams.delete(key)
  for (const [key, value] of Object.entries(params)) {
    if (value) url.searchParams.set(key, value)
  }
  return url
}

export function routeUrl(path: string, params: Record<string, string | null> = {}, replace = false): void {
  const url = targetUrl(path, params)
  if (url.href === window.location.href) return
  const method = replace ? 'replaceState' : 'pushState'
  window.history[method](null, '', `${url.pathname}${url.search}${url.hash}`)
}

/** `routeUrl(path)`가 쓸 주소. 링크의 href에 넣어 새 탭으로 열어도 같은 화면이 나오게 한다. */
export function routeHref(path: string): string {
  const url = targetUrl(path, {})
  return `${url.pathname}${url.search}`
}

/** 보조 키 없이 누른 왼쪽 클릭인지. 새 탭·새 창으로 여는 클릭은 브라우저에 맡긴다. */
export function isPlainClick(event: {
  button: number
  metaKey: boolean
  ctrlKey: boolean
  shiftKey: boolean
  altKey: boolean
}): boolean {
  return event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey
}

/** 신청자 화면의 첫 화면은 사업 찾기다. */
export function goToHome(): void {
  routeUrl('/')
}
