/**
 * 새 신청 알림 뱃지의 계산. 서버를 바꾸지 않고, 이 브라우저에서 마지막으로 본 신청 수와
 * 지금 신청 수의 차이를 센다.
 */
export type SeenCounts = Record<number, number>

const KEY = 'officer-seen-application-counts'

/** 사업별 새 신청 수. 처음 보는 사업과 줄어든 사업은 0이다. */
export function newApplicationCounts(
  postings: readonly { id: number; application_count: number }[], seen: SeenCounts,
): Record<number, number> {
  const result: Record<number, number> = {}
  for (const item of postings) {
    const before = seen[item.id]
    result[item.id] = before === undefined ? 0 : Math.max(0, item.application_count - before)
  }
  return result
}

/** 뱃지 글자. 두 자리를 넘으면 99+로 줄인다. */
export function badgeLabel(count: number): string {
  return count > 99 ? '99+' : String(count)
}

export function readSeenCounts(): SeenCounts {
  try {
    const value: unknown = JSON.parse(window.localStorage.getItem(KEY) || '{}')
    if (!value || typeof value !== 'object' || Array.isArray(value)) return {}
    const result: SeenCounts = {}
    for (const [id, count] of Object.entries(value)) {
      if (/^[1-9]\d*$/.test(id) && Number.isSafeInteger(count) && (count as number) >= 0) result[Number(id)] = count as number
    }
    return result
  } catch { return {} }
}

export function writeSeenCounts(counts: SeenCounts): void {
  try { window.localStorage.setItem(KEY, JSON.stringify(counts)) } catch { /* 저장하지 못하면 다음 방문에 기준을 새로 잡는다 */ }
}
