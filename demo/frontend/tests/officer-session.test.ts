import assert from 'node:assert/strict'
import test from 'node:test'
import { officerReturnPath, officerLoginUrl } from '../src/officer-session.ts'
import { fetchOfficerPosting, fetchOfficerPostings, fetchReasonExplanation } from '../src/api.ts'

test('session return paths remain on officer screens', () => {
  for (const path of ['https://example.test', '//example.test', '/apply', '/officer/login?returnTo=/officer']) assert.equal(officerReturnPath(path), '/officer')
  assert.equal(officerReturnPath('/officer/programs/4/applications/8?role=province'), '/officer/programs/4/applications/8?role=province')
  assert.equal(officerLoginUrl('/officer/programs/4'), '/officer/login?returnTo=%2Fofficer%2Fprograms%2F4')
})

test('forced mock program registry works without backend requests', async () => {
  const originalWindow = globalThis.window
  const originalFetch = globalThis.fetch
  globalThis.window = { location: { search: '?mock=1' } } as Window & typeof globalThis
  let calls = 0
  globalThis.fetch = () => { calls += 1; throw new Error('Unexpected backend request') }
  try {
    const list = await fetchOfficerPostings()
    assert.equal(list.length, 1)
    assert.equal(list[0].builtin, true)
    assert.ok(list[0].application_count > 0)
    assert.equal((await fetchOfficerPosting(list[0].id)).id, list[0].id)
    assert.ok((await fetchReasonExplanation(900001, 'province')).basis)
    assert.equal(calls, 0)
  } finally { globalThis.window = originalWindow; globalThis.fetch = originalFetch }
})
