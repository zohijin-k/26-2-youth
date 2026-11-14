import assert from 'node:assert/strict'
import test from 'node:test'
import { splitEmphasis } from '../src/lib/emphasis.ts'

test('multiple paired markers become strong text without losing punctuation', () => {
  assert.deepEqual(splitEmphasis('귀하는 **전북 내 거주**하는 **청년**입니까?'), [
    { text: '귀하는 ', strong: false }, { text: '전북 내 거주', strong: true },
    { text: '하는 ', strong: false }, { text: '청년', strong: true }, { text: '입니까?', strong: false },
  ])
})

test('unpaired markers and empty bold remain literal text', () => {
  assert.deepEqual(splitEmphasis('문항 **미완료'), [{ text: '문항 **미완료', strong: false }])
  assert.deepEqual(splitEmphasis('****'), [{ text: '****', strong: false }])
})

test('HTML-looking input is retained as text for safe React rendering', () => {
  assert.deepEqual(splitEmphasis('**<img onerror=alert(1)>**'), [{ text: '<img onerror=alert(1)>', strong: true }])
})
