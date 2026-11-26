/**
 * youth 담당자 화면의 확인 사유·판독값 표시 (11-27).
 *
 * 일반 화면에는 한국어 분류·제목·설명만 보인다. 내부 판정 코드(SCAN_UNVERIFIED, ADDRESS_HISTORY_INCOMPLETE 등)와
 * 엔진이 저장한 원문은 지우지 않고 '감사·진단 정보'(diagnostics)로만 넘긴다.
 * 분류·제목·설명은 백엔드 review_reasons가 응답 때 붙인다(`finding_views`, `ai.reasons`).
 */

/** 주소이력불확실사유 코드 → 담당자 문구 (backend review_reasons.ADDRESS_UNCERTAIN_LABELS와 같다). "누락"으로 단정하지 않는다. */
export const ADDRESS_UNCERTAIN_LABELS: Record<string, string> = {
  NUMBER_GAP: '주소이력 순번이 중간에 이어지지 않음',
  NUMBER_UNREADABLE: '주소이력 순번을 읽지 못함',
  EMPTY_PAGE: '이력 줄을 하나도 읽지 못한 쪽이 있음',
  TABLE_NOT_FOUND: '다음 쪽의 이력 표를 찾지 못함',
  ROWS_UNREADABLE: '다음 쪽 이력 줄을 다 읽지 못함',
  NUMBER_START: '주소이력 순번이 1로 시작하지 않음',
  UNREAD_ROWS: '표를 찾지 못한 쪽에 이력 번호가 보임',
  END_UNCONFIRMED: '마지막 이력 아래 끝 표시(이하 여백·다음 구역)를 확인하지 못함',
  SCAN_UNVERIFIED: '스캔 주민등록초본의 주소이력 완전성 확인 필요 — 주소이력의 끝부분이 모두 제출됐는지 자동으로 확정할 수 없어 담당자 확인이 필요합니다.',
}

/** 판독 칸 이름 → 담당자 화면 이름. 없는 칸은 원래 이름을 쓴다. */
const FIELD_LABELS: Record<string, string> = {
  주소이력불확실사유: '주소이력 확인 필요 사유',
  주소이력끝근거: '주소이력 끝 확인 근거',
  주소이력상태: '주소이력 판독 상태',
}

const CODE_TOKEN = /\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b/g

/** 문장에 섞인 영문 코드를 지운다. 코드는 진단 정보에서만 보인다. */
export function plainText(text: string | null | undefined): string {
  return (text ?? '').replace(CODE_TOKEN, '').replace(/\(\s*[,·:]?\s*\)/g, '').replace(/\s{2,}/g, ' ').trim()
}

export interface FieldDisplay {
  label: string
  /** 일반 화면 값. 영문 코드가 없다. */
  items: string[]
  /** 감사·진단: 저장된 원래 값(코드 포함). 일반 값과 같으면 null. */
  diagnostic: string | null
}

export function fieldDisplay(key: string, value: string): FieldDisplay {
  const label = FIELD_LABELS[key] ?? key
  if (key === '주소이력불확실사유') {
    const codes = value.split(',').map((code) => code.trim()).filter(Boolean)
    const items = [...new Set(codes.map((code) => ADDRESS_UNCERTAIN_LABELS[code] ?? '그 밖의 사유 (진단 정보 참고)'))]
    return { label, items: items.length ? items : ['없음'], diagnostic: value }
  }
  const shown = plainText(value)
  return { label, items: [shown || (value ? '코드 값 (진단 정보 참고)' : '-')], diagnostic: shown === value ? null : value }
}

export interface ReasonLike {
  code?: string | null
  title?: string | null
  message?: string | null
  explanation?: string | null
  category_label?: string | null
  details?: string[] | null
  detail?: string | null
  how_to_fix?: string | null
  priority?: number | null
  stored_message?: string | null
  origin?: { code?: string | null; message?: string | null } | null
}

export interface ReasonDisplay {
  category: string | null
  title: string | null
  body: string
  details: string[]
  /** 감사·진단 계층: 내부 코드와 엔진 원문. 일반 화면에서는 접어 둔다. */
  diagnostics: string[]
}

export function reasonDisplay(item: ReasonLike): ReasonDisplay {
  const body = plainText(item.explanation || item.message)
  const title = plainText(item.title) || null
  return {
    category: plainText(item.category_label) || null,
    title: title && title !== body ? title : null,
    body,
    details: (item.details ?? []).map(plainText).filter(Boolean),
    diagnostics: [
      item.code ? `판정 코드: ${item.code}` : '',
      item.origin?.code ? `자동 판정 기록: ${item.origin.code} — ${plainText(item.origin.message)}` : '',
      item.stored_message && plainText(item.stored_message) !== body ? `저장된 안내 문구: ${item.stored_message}` : '',
      item.detail ? `세부: ${item.detail}` : '',
    ].filter(Boolean),
  }
}

/** 담당자가 먼저 확인할 사유: 백엔드 우선순위 1번(없으면 첫 사유). */
export function primaryReason<T extends ReasonLike>(reasons: readonly T[]): T | null {
  return reasons.find((reason) => reason.priority === 1) ?? reasons[0] ?? null
}

const STAGE_LABELS: Record<string, string> = { PASS: '적합', NEEDS_REVIEW: '확인필요', FAIL: '부적합' }

/** 1·2단계 판정 상태 → 한국어. 모르는 값은 코드 대신 '판정 없음'. */
export function stageLabel(status: string | null | undefined): string {
  if (!status) return '-'
  return STAGE_LABELS[status] ?? '판정 없음'
}
