import assert from 'node:assert/strict'
import test from 'node:test'
import { genericPostingId } from '../src/lib/program-route.ts'

test('public API query link selects the published program', () => {
  assert.equal(genericPostingId('/apply/identity', '?posting=12'), 12)
})
test('canonical paths preserve program selection on refresh and take priority over stale query', () => {
  assert.equal(genericPostingId('/apply/programs/9/forms', ''), 9)
  assert.equal(genericPostingId('/apply/programs/9/mypage', '?posting=12'), 9)
})
test('builtin identity and finder routes do not select a generic program', () => {
  assert.equal(genericPostingId('/apply/identity', ''), null)
  assert.equal(genericPostingId('/', '?posting=12'), null)
})
test('invalid IDs never become generic application codes', () => {
  for (const value of ['0', '-1', '1e2', '1.5', '9007199254740992', 'abc']) {
    assert.equal(genericPostingId('/apply/identity', '?posting=' + value), null)
  }
})
