import assert from 'node:assert/strict'
import test from 'node:test'
import { badgeLabel, newApplicationCounts } from '../src/pages/officer/officer-badges.ts'

test('new application badges count only arrivals since the last seen count', () => {
  const postings = [{ id: 1, application_count: 12 }, { id: 2, application_count: 3 }, { id: 3, application_count: 5 }]
  assert.deepEqual(newApplicationCounts(postings, { 1: 9, 2: 7 }), { 1: 3, 2: 0, 3: 0 })
})

test('badge labels cap at 99+', () => {
  assert.equal(badgeLabel(7), '7')
  assert.equal(badgeLabel(99), '99')
  assert.equal(badgeLabel(100), '99+')
})
