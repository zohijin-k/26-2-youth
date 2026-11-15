import assert from 'node:assert/strict'
import test from 'node:test'
import { createModernNavigationRegistration } from '../src/pages/officer/officer-navigation-context.ts'

test('modern logout ownership lasts until the final drawer unmounts and cleanup is idempotent', () => {
  const counts: number[] = []
  const register = createModernNavigationRegistration((count) => counts.push(count))
  const first = register()
  const second = register()
  first()
  first()
  second()
  assert.deepEqual(counts, [1, 2, 1, 0])
  const next = register()
  next()
  assert.deepEqual(counts, [1, 2, 1, 0, 1, 0])
})
