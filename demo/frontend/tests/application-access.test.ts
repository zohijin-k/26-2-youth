import assert from 'node:assert/strict'
import test from 'node:test'
import { fetchApplication } from '../src/api.ts'

test('old owner scope uses the existing asset path once and retries the protected read', async () => {
  const original = globalThis.fetch
  const paths: string[] = []
  globalThis.fetch = async (path) => {
    paths.push(String(path))
    if (paths.length === 1) return new Response('{}', { status: 403 })
    return new Response(JSON.stringify(paths.length === 3 ? { id: 7 } : {}), { status: 200 })
  }
  try {
    assert.equal((await fetchApplication(7)).id, 7)
    assert.deepEqual(paths, ['/api/applications/7', '/api/applications/7/forms/files/original-hwp/options', '/api/applications/7'])
  } finally { globalThis.fetch = original }
})

test('public metadata alone cannot turn an unauthorized application into a successful read', async () => {
  const original = globalThis.fetch
  let calls = 0
  globalThis.fetch = async () => { calls += 1; return new Response('{}', { status: calls === 2 ? 200 : 403 }) }
  try { await assert.rejects(fetchApplication(8), /403/); assert.equal(calls, 3) }
  finally { globalThis.fetch = original }
})
