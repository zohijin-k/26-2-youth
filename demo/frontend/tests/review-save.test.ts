import assert from 'node:assert/strict'
import test from 'node:test'
import { HttpError } from '../src/lib/http-error.ts'
import { reviewSaveError } from '../src/pages/officer/review-save.ts'
import { officerSessionResponse } from '../src/officer-session.ts'
import { postDecision } from '../src/api.ts'

test('save failures keep status distinct and never expose server diagnostics', () => {
  const messages = [409, 500, 503].map(status => reviewSaveError(new HttpError(status, 'private SQL / secret')))
  for (const [i, status] of [409, 500, 503].entries()) {
    assert.ok(messages[i].includes(String(status)))
    assert.ok(messages[i].includes('메모는 유지'))
    assert.ok(!messages[i].includes('private'))
  }
  assert.equal(new Set(messages).size, 3)
  assert.match(reviewSaveError(new DOMException('private timeout', 'TimeoutError')), /시간이 초과/)
  assert.match(reviewSaveError(new TypeError('private socket error')), /연결하지 못해/)
})

test('only actual unauthorized response expires an officer session', () => {
  const previous = globalThis.window
  const events: string[] = []
  globalThis.window = { dispatchEvent: (event: Event) => { events.push(event.type); return true } } as Window & typeof globalThis
  try {
    for (const status of [200, 403, 409, 500, 503]) officerSessionResponse('/api/officer/applications/7/decision', { status })
    assert.deepEqual(events, [])
    officerSessionResponse('/api/officer/applications/7/decision', { status: 401 })
    assert.deepEqual(events, ['officer-session-expired'])
  } finally { globalThis.window = previous }
})

test('real decision HTTP failure preserves status and has a bounded request', async () => {
  const previousWindow = globalThis.window
  const previousFetch = globalThis.fetch
  globalThis.window = { location: { search: '?mock=0' }, dispatchEvent: () => true } as unknown as Window & typeof globalThis
  let calls = 0
  globalThis.fetch = async (_input, init) => {
    calls += 1
    assert.ok(init?.signal instanceof AbortSignal)
    return new Response('{"detail":"private exception"}', { status: 503 })
  }
  try {
    await assert.rejects(postDecision(7, { role: 'province', decision: 'hold', memo: '합성 메모', expected_revision: 1 }), (error: unknown) => error instanceof HttpError && error.status === 503 && !error.message.includes('private'))
    assert.equal(calls, 1)
  } finally { globalThis.window = previousWindow; globalThis.fetch = previousFetch }
})
