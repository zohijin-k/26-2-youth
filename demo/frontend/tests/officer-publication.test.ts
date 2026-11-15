import test from 'node:test'
import assert from 'node:assert/strict'
import { publishReviewedProgram } from '../src/pages/officer/officer-publication.ts'

test('publication persists the reviewed edits and refreshes blockers before publishing', async () => {
  const calls: string[] = []
  const data = { publish_blockers: [] as string[], revision: 2 }
  const result = await publishReviewedProgram({
    save: async () => { calls.push('save') },
    refresh: async () => { calls.push('refresh'); return data },
    publish: async () => { calls.push('publish') },
  })
  assert.deepEqual(calls, ['save', 'refresh', 'publish'])
  assert.equal(result.published, true)
  assert.equal(result.data, data)
})
test('fresh server publication blockers stop publication and remain available for display', async () => {
  const blockers = ['서식을 확정해 주세요.']
  let published = false
  const result = await publishReviewedProgram({
    save: async () => undefined,
    refresh: async () => ({ publish_blockers: blockers }),
    publish: async () => { published = true },
  })
  assert.equal(published, false)
  assert.equal(result.published, false)
  assert.deepEqual(result.blockers, blockers)
})
test('a failed save never attempts a refresh or publication', async () => {
  let nextCalls = 0
  await assert.rejects(publishReviewedProgram({
    save: async () => { throw new Error('저장 실패') },
    refresh: async () => { nextCalls += 1; return {} },
    publish: async () => { nextCalls += 1 },
  }), /저장 실패/)
  assert.equal(nextCalls, 0)
})

test('leaving the editor after saving prevents subsequent publication requests', async () => {
  let current = true
  let nextCalls = 0
  await assert.rejects(publishReviewedProgram({
    save: async () => { current = false },
    refresh: async () => { nextCalls += 1; return {} },
    publish: async () => { nextCalls += 1 },
    isCurrent: () => current,
  }), { name: 'AbortError' })
  assert.equal(nextCalls, 0)
})

test('missing or malformed fresh blockers fail closed', async () => {
  for (const data of [{}, { publish_blockers: null }, { publish_blockers: '확인 필요' }, { publish_blockers: [null] }]) {
    let published = false
    const result = await publishReviewedProgram({
      save: async () => undefined,
      refresh: async () => data as { publish_blockers?: string[] },
      publish: async () => { published = true },
    })
    assert.equal(published, false)
    assert.equal(result.published, false)
    assert.deepEqual(result.blockers, ['게시 조건을 확인하지 못했습니다. 다시 시도해 주세요.'])
  }
})
