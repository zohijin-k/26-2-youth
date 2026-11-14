/**
 * 신청 목록의 구분과 일괄 처리 규칙. 화면·목업이 함께 쓰고, 백엔드 `api/officer.py`의
 * `queue_of`·`decide_bulk`와 같은 규칙이다.
 */
import type { DecisionKey, OfficerQueue } from '../../api.ts'

/** 신청 건의 구분. 판단이 있으면(보류 포함) 처리 완료, 없으면 자동 판정이 적합인 건만 적합이다. */
export const queueOf = (row: { decision: DecisionKey | null; ai_status: string | null }): OfficerQueue =>
  row.decision ? 'done' : row.ai_status === 'PASS' ? 'pass' : 'needs_check'

/**
 * 이 구분에서 보일 일괄 처리 버튼.
 *
 * 확인 필요 구분에서는 승인(역할에 따라 최종 선정·1차 선발)을 일괄로 할 수 없다 — 서류를
 * 보지 않은 통과를 막는다. 보류·반려만 남는다.
 */
export const bulkActionsFor = <T extends { key: DecisionKey }>(queue: OfficerQueue, actions: readonly T[]): T[] =>
  queue === 'needs_check' ? actions.filter((action) => action.key !== 'approve') : [...actions]

/** 일괄 승인에서 걸리는 건(확인 필요 구분)의 신청번호. 승인이 아니면 빈 목록이다. */
export const blockedBulkApprove = (
  decision: DecisionKey,
  rows: readonly { application_no: string; decision: DecisionKey | null; ai_status: string | null }[],
): string[] =>
  decision === 'approve' ? rows.filter((row) => queueOf(row) === 'needs_check').map((row) => row.application_no) : []

/** 백엔드 409와 같은 문장. */
export const bulkApproveRefusal = (label: string, numbers: readonly string[]) =>
  `확인 필요 건은 일괄로 ${label}할 수 없습니다. 심사 화면에서 서류를 확인한 뒤 건별로 처리해 주세요: ${numbers.join(', ')}`
