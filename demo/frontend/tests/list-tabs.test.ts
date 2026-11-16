import assert from 'node:assert/strict'
import test from 'node:test'
import { LIST_TABS, nextTab, shownTabOf, tabCount, tabOf, tabQuery } from '../src/pages/officer/list-tabs.ts'

test('반려 tab is the done queue filtered to rejections and sits right after 처리 완료', () => {
  assert.deepEqual(LIST_TABS, ['needs_check', 'pass', 'done', 'rejected'])
  assert.deepEqual(tabQuery('rejected'), { queue: 'done', status: 'reject' })
  assert.deepEqual(tabQuery('done'), { queue: 'done', status: undefined })
  assert.equal(tabOf({ queue: 'done', status: 'reject' }), 'rejected')
  assert.equal(tabOf({ queue: 'done' }), 'done')
  assert.equal(tabOf({ status: 'reject' }), 'needs_check')
  assert.equal(tabOf({}), 'needs_check')
})

test('tab counts and keyboard movement cover all four tabs', () => {
  const list = { queues: { needs_check: 3, pass: 2, done: 4 }, rejected: 1 }
  assert.deepEqual(LIST_TABS.map((tab) => tabCount(list, tab)), [3, 2, 4, 1])
  assert.equal(tabCount({ queues: list.queues }, 'rejected'), 0)
  assert.equal(nextTab('done', 'ArrowRight'), 'rejected')
  assert.equal(nextTab('rejected', 'ArrowRight'), 'needs_check')
  assert.equal(nextTab('needs_check', 'ArrowLeft'), 'rejected')
  assert.equal(nextTab('pass', 'End'), 'rejected')
  assert.equal(nextTab('pass', 'Enter'), null)
})

test('table shape follows the filters the server applied, not the tab just clicked', () => {
  assert.equal(shownTabOf({ filters: { applied: { queue: 'done', status: 'reject' } } }), 'rejected')
  assert.equal(shownTabOf({ filters: { applied: { queue: 'needs_check', status: null } } }), 'needs_check')
  assert.equal(shownTabOf({ filters: { applied: { queue: null, status: null } } }), null)
  assert.equal(shownTabOf(null), null)
})
