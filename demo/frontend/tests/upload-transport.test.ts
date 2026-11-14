import assert from 'node:assert/strict'
import test from 'node:test'
import { uploadDocument } from '../src/api.ts'

class FakeRequest {
  static latest: FakeRequest
  upload: {onprogress?: (event: {lengthComputable: boolean; loaded: number; total: number}) => void; onload?: () => void} = {}
  onload?: () => void
  onerror?: () => void
  onabort?: () => void
  status = 0
  response: unknown
  responseType = ''
  method = ''
  path = ''
  body: FormData | null = null
  constructor() { FakeRequest.latest = this }
  open(method: string, path: string) { this.method = method; this.path = path }
  send(body: FormData) { this.body = body }
  abort() { this.onabort?.() }
  respond(status: number, body: unknown) { this.status = status; this.response = body; this.onload?.() }
}

test('multipart contract, real progress and slow processing preserve the pending request', async () => {
  const original = globalThis.XMLHttpRequest
  globalThis.XMLHttpRequest = FakeRequest as unknown as typeof XMLHttpRequest
  try {
    const progress: number[][] = []
    let sent = false
    let resolved = false
    const promise = uploadDocument(7, 'resident_abstract', new File(['synthetic'], 'synthetic.pdf'), '2026-11-14', {
      signal: new AbortController().signal, onProgress: (loaded, total) => progress.push([loaded, total]), onSent: () => { sent = true },
    }).then((value) => { resolved = true; return value })
    const request = FakeRequest.latest
    assert.equal(request.method, 'POST')
    assert.equal(request.path, '/api/applications/7/documents')
    assert.deepEqual([...request.body!.keys()], ['file', 'slot_key', 'declared_issue_date'])
    assert.equal((request.body!.get('file') as File).name, 'synthetic.pdf')
    request.upload.onprogress!({lengthComputable: false, loaded: 1, total: 0})
    request.upload.onprogress!({lengthComputable: true, loaded: 5, total: 10})
    assert.deepEqual(progress, [[5, 10]])
    request.upload.onload!()
    await new Promise((resolve) => setTimeout(resolve, 30))
    assert.equal(sent, true)
    assert.equal(resolved, false)
    const doc = {document_id: 41, slot_key: 'resident_abstract', status: 'PASS'}
    request.respond(200, doc)
    assert.deepEqual(await promise, doc)
  } finally { globalThis.XMLHttpRequest = original }
})

test('failed and aborted uploads reject without fabricating a result', async () => {
  const original = globalThis.XMLHttpRequest
  globalThis.XMLHttpRequest = FakeRequest as unknown as typeof XMLHttpRequest
  try {
    const options = () => ({signal: new AbortController().signal, onProgress: () => {}, onSent: () => {}})
    const failed = uploadDocument(1, 'slot', new File(['x'], 'test.pdf'), '', options())
    FakeRequest.latest.respond(422, {detail: '발급일을 확인해 주세요.'})
    await assert.rejects(failed, /발급일을 확인해 주세요/)
    const controller = new AbortController()
    const aborted = uploadDocument(1, 'slot', new File(['x'], 'test.pdf'), '', {...options(), signal: controller.signal})
    controller.abort()
    await assert.rejects(aborted, {name: 'AbortError'})
    const already = new AbortController()
    already.abort()
    await assert.rejects(uploadDocument(1, 'slot', new File(['x'], 'test.pdf'), '', {...options(), signal: already.signal}), {name: 'AbortError'})
  } finally { globalThis.XMLHttpRequest = original }
})
