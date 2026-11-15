import assert from 'node:assert/strict'
import test from 'node:test'
import { DEFAULT_FIELD_SIZE, snappedField } from '../src/lib/form-snap.ts'

const page = { width: 500, height: 400 }

test('a null snap response adds the default-size text box at the click', () => {
  assert.deepEqual(snappedField({ box: null }, { x: 100, y: 50 }, page),
    { box: [100, 50, 100 + DEFAULT_FIELD_SIZE.width, 50 + DEFAULT_FIELD_SIZE.height], field_type: 'text', type: 'text', label: '새 입력칸' })
  assert.deepEqual(snappedField(null, { x: 100, y: 50 }, page).box, [100, 50, 220, 70])
})

test('a default box near the page edge stays inside the page', () => {
  const box = snappedField(null, { x: 495, y: 399 }, page).box
  assert.ok(box[0] >= 0 && box[2] <= 500 && box[3] <= 400)
  assert.equal(box[2] - box[0], DEFAULT_FIELD_SIZE.width)
})

test('a snap suggestion keeps its box and maps the rendering type', () => {
  assert.deepEqual(snappedField({ box: [10, 20, 90, 40], field_type: 'signature', label: ' (인) ' }, { x: 50, y: 30 }, page),
    { box: [10, 20, 90, 40], field_type: 'signature', type: 'image', label: '(인)' })
  const unknown = snappedField({ box: [10, 20, 90, 40], field_type: 'other', label: 'x'.repeat(300) }, { x: 50, y: 30 }, page)
  assert.equal(unknown.field_type, 'text')
  assert.equal(unknown.label.length, 200)
})
