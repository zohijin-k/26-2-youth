import { blockedBulkApprove, bulkActionsFor, queueOf } from './bulk-actions.ts'

const fail = (message: string): never => { throw new Error(message) }
const same = (actual: unknown, expected: unknown, what: string) => {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    fail(`${what}: got ${JSON.stringify(actual)}, expected ${JSON.stringify(expected)}`)
  }
}

const ROW = (application_no: string, decision: 'approve' | 'hold' | 'reject' | null, ai_status: string | null) =>
  ({ application_no, decision, ai_status })

// queueOf
same(queueOf(ROW('A', null, null)), 'needs_check', 'not reviewed')
same(queueOf(ROW('A', null, 'NEEDS_REVIEW')), 'needs_check', 'needs review')
same(queueOf(ROW('A', null, 'FAIL')), 'needs_check', 'fail')
same(queueOf(ROW('A', null, 'PASS')), 'pass', 'pass')
same(queueOf(ROW('A', 'hold', 'FAIL')), 'done', 'held')
same(queueOf(ROW('A', 'approve', 'PASS')), 'done', 'approved')

// bulkActionsFor: 확인 필요 탭에서는 보류·반려만
const actions = [{ key: 'approve' as const }, { key: 'hold' as const }, { key: 'reject' as const }]
same(bulkActionsFor('needs_check', actions).map((a) => a.key), ['hold', 'reject'], 'needs_check tab')
same(bulkActionsFor('pass', actions).map((a) => a.key), ['approve', 'hold', 'reject'], 'pass tab')
same(bulkActionsFor('done', actions).map((a) => a.key), ['approve', 'hold', 'reject'], 'done tab')

// blockedBulkApprove: 승인일 때만 확인 필요 건을 고른다
const rows = [ROW('P', null, 'PASS'), ROW('N', null, 'NEEDS_REVIEW'), ROW('U', null, null), ROW('H', 'hold', 'FAIL')]
same(blockedBulkApprove('approve', rows), ['N', 'U'], 'approve blocks needs_check rows')
same(blockedBulkApprove('hold', rows), [], 'hold is never blocked')
same(blockedBulkApprove('reject', rows), [], 'reject is never blocked')
same(blockedBulkApprove('approve', [rows[0], rows[3]]), [], 'pass and decided rows may be approved')

console.log('bulk-actions: ok')
