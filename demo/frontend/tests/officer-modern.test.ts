import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { canStartPublication, evidencePresentation, menuKeyResult, officerLabel, restorePanelFocus } from '../src/pages/officer/officer-modern-model.ts'

function declarations(css: string): Record<string, string> {
  return Object.fromEntries([...css.matchAll(/(--[\w-]+)\s*:\s*([^;{}]+);/g)].map((match) => [match[1], match[2].trim()]))
}
test('officer scoped tokens keep every applicant token name and value', () => {
  const applicant = readFileSync(new URL('../src/styles/tokens.css', import.meta.url), 'utf8')
  const officer = readFileSync(new URL('../src/pages/officer/officer-modern-tokens.css', import.meta.url), 'utf8')
  assert.deepEqual(declarations(officer), declarations(applicant))
  assert.equal(officer.includes(':root'), false)
  assert.match(officer, /\.om\s*\{/)
})
test('publication stays blocked while any individual confirmation remains', () => {
  assert.equal(canStartPublication({ pendingCount: 1, formsConfirmed: true }), false)
})
test('unsaved analysis edits may start the save-before-publish transaction', () => {
  assert.equal(canStartPublication({ pendingCount: 0, formsConfirmed: true, draftDirty: true }), true)
})
test('unconfirmed or unsaved templates cannot start publication', () => {
  assert.equal(canStartPublication({ pendingCount: 0, formsConfirmed: false }), false)
  assert.equal(canStartPublication({ pendingCount: 0, formsConfirmed: true, layoutDirty: true }), false)
  assert.equal(canStartPublication({ pendingCount: 0, formsConfirmed: true, busy: true }), false)
})
test('pending evidence shows one-line preview while confirmed evidence starts collapsed', () => {
  assert.deepEqual(evidencePresentation({ needs_review: true, confidence: 0.8, quote: '공고문 근거' }), { showPreview: true, expanded: false, chip: null })
  assert.deepEqual(evidencePresentation({ needs_review: false, confidence: 0.8, quote: '공고문 근거' }), { showPreview: false, expanded: false, chip: null })
})
test('weak and manual evidence have labels without exposing confidence numbers', () => {
  assert.equal(evidencePresentation({ needs_review: true, source: 'manual', confidence: 0 }).chip, '근거 없음·직접 입력')
  assert.equal(evidencePresentation({ needs_review: true, confidence: 0.59 }).chip, '근거 약함')
  assert.equal(evidencePresentation({ needs_review: true, confidence: 0.6 }).chip, null)
})
test('menu keyboard closes on Escape and cycles arrows and trapped Tab', () => {
  assert.deepEqual(menuKeyResult('Escape', 1, 3), { kind: 'close' })
  assert.deepEqual(menuKeyResult('ArrowDown', 2, 3), { kind: 'focus', index: 0 })
  assert.deepEqual(menuKeyResult('ArrowUp', 0, 3), { kind: 'focus', index: 2 })
  assert.deepEqual(menuKeyResult('Tab', 0, 3, true), { kind: 'focus', index: 2 })
  assert.deepEqual(menuKeyResult('Home', 2, 3), { kind: 'focus', index: 0 })
  assert.deepEqual(menuKeyResult('End', 0, 3), { kind: 'focus', index: 2 })
})
test('internal review status and reader values receive Korean labels', () => {
  assert.equal(officerLabel('NEEDS_REVIEW'), '확인 필요')
  assert.equal(officerLabel('PASS'), '충족')
  assert.equal(officerLabel('FAIL'), '미충족')
  assert.equal(officerLabel('pdftext'), '문서 글자 읽기')
  assert.equal(officerLabel('unrecognized_engine_value'), '확인 필요')
  assert.equal(officerLabel('이미 확인한 한글 사유'), '이미 확인한 한글 사유')
})

test('closing a panel returns focus to its connected opener', () => {
  let focused = 0
  restorePanelFocus({ isConnected: true, focus: () => { focused += 1 } })
  assert.equal(focused, 1)
  restorePanelFocus({ isConnected: false, focus: () => { focused += 1 } })
  restorePanelFocus(null)
  assert.equal(focused, 1)
})
