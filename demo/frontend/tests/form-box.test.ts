import assert from 'node:assert/strict'
import test from 'node:test'
import { boundedBox, movedBox } from '../src/lib/form-box.ts'

test('a reversed drawn box stays inside the PDF and keeps positive area', () => {
  assert.deepEqual(boundedBox([110, 90, -10, -20], { width: 100, height: 80 }), [0, 0, 100, 80])
  const box = boundedBox([100, 80, 100, 80], { width: 100, height: 80 })
  assert.ok(box[0] < box[2] && box[1] < box[3])
  assert.ok(box[2] <= 100 && box[3] <= 80)
})

test('moving a field against any edge preserves its dimensions', () => {
  const page = { width: 100, height: 80 }
  assert.deepEqual(movedBox([10, 10, 40, 30], -100, 100, page), [0, 60, 30, 80])
  assert.deepEqual(movedBox([10, 10, 40, 30], 100, -100, page), [70, 0, 100, 20])
})
