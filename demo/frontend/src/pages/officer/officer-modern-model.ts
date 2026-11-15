import { routeHref } from '../../navigation-url.ts'

/** Presentation helpers only: server publication/selection checks remain authoritative. */
export const OFFICER_LABELS: Readonly<Record<string, string>> = {
  NEEDS_REVIEW: '확인 필요', PASS: '충족', FAIL: '미충족', UNKNOWN: '확인 필요',
  NOT_APPLICABLE: '해당 없음', ERROR: '확인 필요', PENDING: '확인 필요',
  draft: '작성 중', published: '게시 중', closed: '마감',
  approve: '선정', hold: '보류', reject: '반려', pending: '처리 전',
  pdftext: '문서 글자 읽기', pdf_text: '문서 글자 읽기', ocr: '이미지 글자 읽기',
  manual: '직접 입력', checklist: '담당자 확인', document: '제출 서류',
  age: '나이 범위', residence: '거주지', issue_date: '서류 발급일',
  work_continuity: '근로 계속성', income: '중위소득',
}
export function officerLabel(value: string | null | undefined, fallback = '확인 필요'): string {
  return value ? OFFICER_LABELS[value] || (/^[\w.:-]+$/.test(value) ? fallback : value) : fallback
}

export interface PublishReadiness {
  busy?: boolean
  pendingCount: number
  formsConfirmed: boolean
  layoutDirty?: boolean
  /** Unsaved analysis changes are saved by the publication transaction. */
  draftDirty?: boolean
}
export function canStartPublication(state: PublishReadiness): boolean {
  return !state.busy && state.pendingCount === 0 && state.formsConfirmed && !state.layoutDirty
}

export function evidencePresentation(item: { needs_review: boolean; source?: string; confidence: number; quote?: string }): {
  showPreview: boolean; expanded: boolean; chip: string | null
} {
  return { showPreview: item.needs_review && !!item.quote, expanded: false,
    chip: item.source === 'manual' ? '근거 없음·직접 입력' : item.confidence < 0.6 ? '근거 약함' : null }
}

export type MenuKeyResult = { kind: 'close' } | { kind: 'focus'; index: number } | { kind: 'none' }
/** Shared by DOM menus/drawers; disabled actions are filtered before passing count. */
export function menuKeyResult(key: string, index: number, count: number, shift = false): MenuKeyResult {
  if (key === 'Escape') return { kind: 'close' }
  if (!count) return { kind: 'none' }
  if (key === 'Home') return { kind: 'focus', index: 0 }
  if (key === 'End') return { kind: 'focus', index: count - 1 }
  if (key === 'ArrowDown' || key === 'ArrowRight') return { kind: 'focus', index: (index + 1 + count) % count }
  if (key === 'ArrowUp' || key === 'ArrowLeft') return { kind: 'focus', index: (index - 1 + count) % count }
  if (key === 'Tab') return { kind: 'focus', index: (index + (shift ? -1 : 1) + count) % count }
  return { kind: 'none' }
}

export function officerDestination(path: string, tab?: string): string {
  const url = new URL(routeHref(path), window.location.origin)
  if (tab) url.searchParams.set('tab', tab)
  return url.pathname + url.search
}

/** Closing a panel restores its opener only while that opener still exists. */
export function restorePanelFocus(previous: { isConnected: boolean; focus: () => void } | null): void {
  if (previous?.isConnected) previous.focus()
}
