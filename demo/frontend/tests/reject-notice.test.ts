import assert from 'node:assert/strict'
import test from 'node:test'
import { NOTICE_INTRO, reasonLines, toggleReason } from '../src/pages/officer/reject-notice.ts'

const reasons = {
  application_id: 1, ai_status: 'FAIL' as const, ai_status_label: '부적합', source: 'rules',
  documents: [
    { slot_key: 'resident_abstract', label: '주민등록초본', status: 'FAIL' as const, status_label: '부적합',
      findings: [{ code: 'A', message: '발급일이   기준일보다 빠릅니다.', severity: 'FAIL' }] },
    { slot_key: 'photo', label: '사진', status: 'NEEDS_REVIEW' as const, status_label: '확인필요', findings: [] },
  ],
  missing: [{ slot_key: 'bank', label: '통장 사본' }],
}

test('every 확인 필요 item becomes one applicant-readable line, without duplicates', () => {
  assert.deepEqual(reasonLines(reasons, ['나이 범위: 기준을 충족하지 못했습니다.', '사진: 서류를 다시 확인해 주세요.']), [
    '주민등록초본: 발급일이 기준일보다 빠릅니다.',
    '사진: 서류를 다시 확인해 주세요.',
    '통장 사본: 필수 서류가 제출되지 않았습니다.',
    '나이 범위: 기준을 충족하지 못했습니다.',
  ])
})

test('picking reasons adds lines under the intro and unpicking removes only that line', () => {
  let notice = toggleReason('', '사유 A', true)
  assert.equal(notice, `${NOTICE_INTRO}\n- 사유 A`)
  notice = toggleReason(notice, '사유 B', true)
  notice = toggleReason(`${notice}\n담당자가 직접 쓴 줄`, '사유 A', false)
  assert.equal(notice, `${NOTICE_INTRO}\n- 사유 B\n담당자가 직접 쓴 줄`)
  assert.equal(toggleReason(notice, '사유 B', true), notice)
})
