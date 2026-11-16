import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { canStartPublication, evidencePresentation, menuKeyResult, officerLabel, restorePanelFocus, suggestionPresentation } from '../src/pages/officer/officer-modern-model.ts'

function declarations(css: string): Record<string, string[]> {
  const tokens: Record<string, string[]> = {}
  for (const match of css.matchAll(/(--[\w-]+)\s*:\s*([^;{}]+);/g)) {
    (tokens[match[1]] ||= []).push(match[2].trim())
  }
  return tokens
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
  assert.deepEqual(evidencePresentation({ needs_review: true, confidence: 0.8, quote: '공고문 근거' }), { showPreview: true, expanded: false, chip: null, hasSource: true })
  assert.deepEqual(evidencePresentation({ needs_review: false, confidence: 0.8, quote: '공고문 근거' }), { showPreview: false, expanded: false, chip: null, hasSource: true })
})
test('weak evidence is labelled without exposing confidence numbers', () => {
  assert.equal(evidencePresentation({ needs_review: true, confidence: 0.59, quote: '공고문 근거' }).chip, '근거 약함')
  assert.equal(evidencePresentation({ needs_review: true, confidence: 0.6, quote: '공고문 근거' }).chip, null)
})
test('officer-entered items show no chip and no source toggle', () => {
  assert.deepEqual(evidencePresentation({ needs_review: true, source: 'manual', confidence: 0 }), { showPreview: false, expanded: false, chip: null, hasSource: false })
  assert.equal(evidencePresentation({ needs_review: true, source: 'manual', confidence: 0, quote: '' }).hasSource, false)
})
test('provider-written guidance is marked as an AI draft until confirmed', () => {
  assert.equal(evidencePresentation({ needs_review: true, confidence: 0, quote: '1. 모집개요', ai_drafted: true }).chip, 'AI 작성 · 공고문과 대조 필요')
  assert.equal(evidencePresentation({ needs_review: false, confidence: 0, quote: '1. 모집개요', ai_drafted: true }).chip, 'AI 작성')
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

test('a reference card is told apart from a suggestion and shows the kind with the read values', () => {
  assert.deepEqual(suggestionPresentation({ type: 'age' }), { chip: 'AI 제안 · 담당자 확인 필요', read: null })
  assert.deepEqual(suggestionPresentation({ type: 'age', reference: false, read: '18~39세' }), { chip: 'AI 제안 · 담당자 확인 필요', read: null })
  assert.deepEqual(suggestionPresentation({ type: 'age', reference: true, read: '18~39세' }), { chip: 'AI 참고 · 담당자가 직접 확인', read: '나이 범위 · 18~39세' })
  assert.deepEqual(suggestionPresentation({ type: 'income', reference: true, read: '60% 이하' }), { chip: 'AI 참고 · 담당자가 직접 확인', read: '중위소득 · 60% 이하' })
  assert.deepEqual(suggestionPresentation({ type: 'unknown_kind', reference: true, read: '값' }), { chip: 'AI 참고 · 담당자가 직접 확인', read: '기준 · 값' })
  assert.deepEqual(suggestionPresentation({ type: 'residence', reference: true }), { chip: 'AI 참고 · 담당자가 직접 확인', read: null })
})
