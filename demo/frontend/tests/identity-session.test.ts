import assert from 'node:assert/strict'
import test from 'node:test'
import { ACTIVE_APPLICATION_KEY, createIdentitySession } from '../src/lib/identity-session.ts'

function setup() {
  const saved = new Map<string, string>()
  const applications = new Map<number, { id: number; program_code: string; application_no: string }>()
  let created = 0
  const storage = { getItem: (key: string) => saved.get(key) ?? null,
    setItem: (key: string, value: string) => { saved.set(key, value) },
    removeItem: (key: string) => { saved.delete(key) } }
  const options = {
    programCode: 'job_package', storage: () => storage,
    load: async (id: number) => {
      const application = applications.get(id)
      if (!application) throw new Error('GET 신청 실패 (404)')
      return application
    },
    create: async (program_code: string) => {
      created += 1
      const application = { id: created, program_code, application_no: `JP-2026-${String(created).padStart(6, '0')}` }
      applications.set(application.id, application)
      return application
    },
  }
  return { options, saved, applications, created: () => created }
}

test('opening identity three times allocates zero applications', async () => {
  const state = setup()
  for (let visit = 0; visit < 3; visit += 1) assert.equal(await createIdentitySession(state.options).restore(), null)
  assert.equal(state.created(), 0)
  assert.equal(state.saved.size, 0)
})

test('identity submission followed by refresh retains application number', async () => {
  const state = setup()
  const submitted = await createIdentitySession(state.options).ensure()
  const refreshed = await createIdentitySession(state.options).restore()
  assert.equal(refreshed?.id, submitted.id)
  assert.equal(refreshed?.application_no, 'JP-2026-000001')
  assert.equal(state.created(), 1)
})

test('concurrent submit and failed verification retry share one allocation', async () => {
  const state = setup()
  const session = createIdentitySession(state.options)
  const [first, concurrent] = await Promise.all([session.ensure(), session.ensure()])
  assert.equal(first.id, concurrent.id)
  // Verification is a later API action. Retrying it must use the allocated ID.
  assert.equal((await session.ensure()).id, first.id)
  assert.equal(state.created(), 1)
})

test('deleted and wrong-program saved IDs do not create replacements on visit', async () => {
  const state = setup()
  state.saved.set(ACTIVE_APPLICATION_KEY, '99')
  assert.equal(await createIdentitySession(state.options).restore(), null)
  assert.equal(state.saved.has(ACTIVE_APPLICATION_KEY), false)
  state.applications.set(77, { id: 77, program_code: 'double_savings', application_no: 'FAKE-77' })
  state.saved.set(ACTIVE_APPLICATION_KEY, '77')
  assert.equal(await createIdentitySession(state.options).restore(), null)
  assert.equal(state.created(), 0)
})

test('load outages never trigger replacement applications', async () => {
  const state = setup()
  state.saved.set(ACTIVE_APPLICATION_KEY, '1')
  const session = createIdentitySession({ ...state.options, load: async () => { throw new Error('FAKE network outage') } })
  await assert.rejects(session.restore(), /network outage/)
  await assert.rejects(session.ensure(), /network outage/)
  assert.equal(state.created(), 0)
})

test('storage-disabled sessions retain the same application for retries', async () => {
  const state = setup()
  const session = createIdentitySession({ ...state.options, storage: () => { throw new Error('FAKE storage disabled') } })
  const first = await session.ensure()
  assert.equal((await session.restore())?.id, first.id)
  assert.equal((await session.ensure()).id, first.id)
  assert.equal(state.created(), 1)
})

test('allocation errors may retry without retaining a rejected promise', async () => {
  const state = setup()
  let fail = true
  const session = createIdentitySession({ ...state.options, create: async (program) => {
    if (fail) { fail = false; throw new Error('FAKE allocation outage') }
    return state.options.create(program)
  } })
  await assert.rejects(session.ensure(), /allocation outage/)
  assert.equal((await session.ensure()).application_no, 'JP-2026-000001')
  assert.equal(state.created(), 1)
})
