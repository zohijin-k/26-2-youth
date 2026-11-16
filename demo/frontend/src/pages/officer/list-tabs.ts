import type { OfficerList, OfficerListQuery, OfficerQueue } from '../../api.ts'

/**
 * 신청 목록 구분 탭. 서버 구분 셋(확인 필요 · 적합 · 처리 완료)에 '반려'를 붙인다.
 * 반려 탭은 처리 완료 가운데 반려한 건만 본다 — 서버에는 queue=done + status=reject로 묻는다.
 */
export type ListTab = OfficerQueue | 'rejected'
export const LIST_TABS: readonly ListTab[] = ['needs_check', 'pass', 'done', 'rejected']

export const tabOf = (query: Pick<OfficerListQuery, 'queue' | 'status'>): ListTab =>
  query.queue === 'done' && query.status === 'reject' ? 'rejected' : query.queue ?? 'needs_check'

export const tabQuery = (tab: ListTab): Pick<OfficerListQuery, 'queue' | 'status'> =>
  tab === 'rejected' ? { queue: 'done', status: 'reject' } : { queue: tab, status: undefined }

export const tabCount = (list: Pick<OfficerList, 'queues' | 'rejected'>, tab: ListTab): number =>
  tab === 'rejected' ? list.rejected ?? 0 : list.queues[tab]

/**
 * 지금 표에 있는 행이 속한 탭. 탭을 막 바꾼 직후에는 이전 목록이 아직 남아 있으므로
 * 표 모양(반려 표인지)은 누른 탭이 아니라 서버가 적용한 조건으로 정한다.
 */
export const shownTabOf = (list: { filters: { applied: { queue?: string | null; status?: string | null } } } | null | undefined): ListTab | null => {
  if (!list) return null
  const { queue, status } = list.filters.applied
  if (queue !== 'needs_check' && queue !== 'pass' && queue !== 'done') return null
  return tabOf({ queue, status: status ?? undefined })
}

/** 키보드로 탭을 옮길 때 다음 탭. 해당 키가 아니면 null. */
export function nextTab(current: ListTab, key: string): ListTab | null {
  const at = LIST_TABS.indexOf(current)
  const last = LIST_TABS.length - 1
  const to = key === 'ArrowRight' ? (at === last ? 0 : at + 1)
    : key === 'ArrowLeft' ? (at === 0 ? last : at - 1)
      : key === 'Home' ? 0 : key === 'End' ? last : -1
  return to < 0 ? null : LIST_TABS[to]
}
