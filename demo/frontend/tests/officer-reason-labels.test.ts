import assert from 'node:assert/strict'
import test from 'node:test'

import { fieldDisplay, primaryReason, reasonDisplay, stageLabel } from '../src/pages/officer/reason-labels.ts'

test('SCAN_UNVERIFIED reads as Korean completeness guidance; the code survives only as diagnostics', () => {
  const shown = fieldDisplay('주소이력불확실사유', 'SCAN_UNVERIFIED')
  assert.equal(shown.label, '주소이력 확인 필요 사유')
  assert.deepEqual(shown.items, ['스캔 주민등록초본의 주소이력 완전성 확인 필요 — 주소이력의 끝부분이 모두 제출됐는지 자동으로 확정할 수 없어 담당자 확인이 필요합니다.'])
  assert.equal(shown.diagnostic, 'SCAN_UNVERIFIED')
  assert.doesNotMatch(shown.items.join(' '), /SCAN_UNVERIFIED|누락/)
})

test('several sub-reasons are listed once each; unknown codes are not echoed on the normal screen', () => {
  const shown = fieldDisplay('주소이력불확실사유', 'END_UNCONFIRMED,SCAN_UNVERIFIED,NEW_FAKE_CODE')
  assert.equal(shown.items.length, 3)
  assert.equal(shown.items[0], '마지막 이력 아래 끝 표시(이하 여백·다음 구역)를 확인하지 못함')
  assert.equal(shown.items[2], '그 밖의 사유 (진단 정보 참고)')
  assert.doesNotMatch(shown.items.join(' '), /[A-Z]{2,}_[A-Z]/)
})

test('ordinary Korean field values are unchanged and carry no diagnostics', () => {
  assert.deepEqual(fieldDisplay('주소이력끝근거', '이하 여백 (3쪽)'), { label: '주소이력 끝 확인 근거', items: ['이하 여백 (3쪽)'], diagnostic: null })
  assert.deepEqual(fieldDisplay('성명', '가상신청'), { label: '성명', items: ['가상신청'], diagnostic: null })
})

test('application reason shows category, title and explanation; engine origin and code are diagnostics only', () => {
  const view = reasonDisplay({
    code: 'ADDRESS_HISTORY_INCOMPLETE', category_label: '서류 완결성 확인 필요',
    title: '스캔 주민등록초본의 주소이력 완전성 확인 필요',
    message: '주소이력의 끝부분이 모두 제출됐는지 자동으로 확정할 수 없어 담당자 확인이 필요합니다.',
    explanation: '주소이력의 끝부분이 모두 제출됐는지 자동으로 확정할 수 없어 담당자 확인이 필요합니다.',
    origin: { code: 'LOW_OCR_CONFIDENCE', message: "'주민등록초본'의 일부 항목이 자동으로 판독되지 않았습니다." },
  })
  assert.equal(view.category, '서류 완결성 확인 필요')
  assert.equal(view.title, '스캔 주민등록초본의 주소이력 완전성 확인 필요')
  assert.doesNotMatch(`${view.category} ${view.title} ${view.body}`, /[A-Z]{2,}_[A-Z]|신뢰도|판독되지 않았/)
  assert.deepEqual(view.diagnostics, [
    '판정 코드: ADDRESS_HISTORY_INCOMPLETE',
    "자동 판정 기록: LOW_OCR_CONFIDENCE — '주민등록초본'의 일부 항목이 자동으로 판독되지 않았습니다.",
  ])
})

test('a raw stored finding without projection still hides its code from the normal line', () => {
  const view = reasonDisplay({ code: 'RECEIPT_MANUAL_REVIEW', message: '결제영수증은 담당자 확인 대상입니다.' })
  assert.equal(view.body, '결제영수증은 담당자 확인 대상입니다.')
  assert.deepEqual(view.diagnostics, ['판정 코드: RECEIPT_MANUAL_REVIEW'])
})

test('primary reason follows backend priority', () => {
  const second = { code: 'B', priority: 2 }
  const first = { code: 'A', priority: 1 }
  assert.equal(primaryReason([second, first]), first)
  assert.equal(primaryReason([]), null)
})

test('stage statuses read in Korean, never as engine codes', () => {
  assert.equal(stageLabel('NEEDS_REVIEW'), '확인필요')
  assert.equal(stageLabel('PASS'), '적합')
  assert.equal(stageLabel('FAIL'), '부적합')
  assert.equal(stageLabel(null), '-')
  assert.equal(stageLabel('SOMETHING_NEW'), '판정 없음')
})
