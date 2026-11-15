/** Real loopback UI journey using generated synthetic documents and isolated storage. */
const { chromium } = await import(process.env.PLAYWRIGHT_PACKAGE ?? '/tmp/renewal-npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright/index.mjs')
import assert from 'node:assert/strict'
import { readFile, writeFile, mkdir } from 'node:fs/promises'

const BASE = process.env.VISUAL_BASE_URL ?? 'http://127.0.0.1:5187'
const BACKEND = process.env.VISUAL_BACKEND_URL ?? 'http://127.0.0.1:8014'
for (const value of [BASE, BACKEND]) assert.ok(['127.0.0.1', 'localhost'].includes(new URL(value).hostname))
const OUTPUT = new URL('./', import.meta.url)
const SHOTS = new URL('./shots/after-journey/', import.meta.url).pathname.replace(/\/$/, '')
await mkdir(SHOTS, { recursive: true })
const fixtures = JSON.parse(await readFile('/tmp/renewal-master2-visual-fixtures/manifest.json', 'utf8'))
const baseline = JSON.parse(await readFile(new URL('../visual-baseline.json', OUTPUT), 'utf8'))
const day = '2026-11-15'
const endDay = '2026-12-31'
const result = { viewport: { width: 1440, height: 900 }, applicant_viewport: { width: 940, height: 1000 }, date: day,
  posting_id: null, application_id: null, application_no: null, job_application_id: null, job_application_no: null,
  counts_before: null, counts_after: null, assertions: [], shots: [], page_errors: [], request_failures: [], errors: [],
  mock_api_requests: [], current_stage: 'starting' }
const browser = await chromium.launch({ headless: true })
const browserOptions = { deviceScaleFactor: 1, locale: 'ko-KR', timezoneId: 'Asia/Seoul', reducedMotion: 'reduce' }
const context = await browser.newContext({ ...browserOptions, viewport: result.viewport })
const applicantContext = await browser.newContext({ ...browserOptions, viewport: result.applicant_viewport })
const officer = await context.newPage()
let applicant
let activePage = officer
let createRequests = 0
track(officer)
function clean(value) { return String(value).replace(/sk-[A-Za-z0-9-]{10,}/g, '[redacted]') }
function track(page) {
  page.on('pageerror', error => result.page_errors.push(clean(error)))
  page.on('requestfailed', request => {
    const url = new URL(request.url())
    result.request_failures.push({ path: ['http:', 'https:'].includes(url.protocol) ? url.pathname : url.protocol,
      error: request.failure()?.errorText })
  })
  page.on('request', request => {
    const url = new URL(request.url())
    if (['http:', 'https:'].includes(url.protocol)) assert.ok(['127.0.0.1', 'localhost'].includes(url.hostname), 'External browser request is forbidden')
    if (page === applicant && request.method() === 'POST' && url.pathname === '/api/applications') createRequests += 1
  })
}
function waitResponse(page, predicate) {
  const pending = page.waitForResponse(predicate)
  void pending.catch(() => undefined)
  return pending
}
function passed(name, detail = true) {
  result.assertions.push({ name, passed: true, detail })
  console.log('PASS ' + name)
}
async function requestJson(actor, path, options = {}) {
  const response = await actor.request.fetch(`${path.startsWith('/__visual__/') ? BACKEND : BASE}${path}`, options)
  assert.ok(response.ok(), `${options.method ?? 'GET'} ${path} returned ${response.status()}`)
  return response.json()
}
const officerJson = (path, options) => requestJson(context, path, options)
const applicantJson = (path, options) => requestJson(applicantContext, path, options)
async function capture(page, name) {
  activePage = page
  result.current_stage = name
  await page.evaluate(async () => {
    await document.fonts.ready
    await Promise.all([...document.images].map(image => image.decode().catch(() => undefined)))
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))
  })
  const path = `${SHOTS}/${name}.png`
  await page.screenshot({ path, fullPage: true, animations: 'disabled' })
  result.shots.push({ name, path, url: page.url() })
}
async function draw(page, canvas) {
  await canvas.scrollIntoViewIfNeeded()
  const box = await canvas.boundingBox()
  assert.ok(box)
  await page.mouse.move(box.x + 20, box.y + 20)
  await page.mouse.down()
  await page.mouse.move(box.x + Math.min(110, box.width - 20), box.y + Math.min(55, box.height - 15), { steps: 10 })
  await page.mouse.move(box.x + Math.min(140, box.width - 10), box.y + 28, { steps: 6 })
  await page.mouse.up()
}

async function showPdfWithViewerControls(page, scope) {
  const viewer = page.locator(scope)
  const canvas = viewer.locator('.viewer__canvas')
  await canvas.waitFor()
  await page.waitForLoadState('networkidle')
  await viewer.getByRole('button', { name: '확대', exact: true }).click()
  await page.waitForFunction(selector => document.querySelector(selector)?.width > 300, `${scope} .viewer__canvas`)
  await page.waitForTimeout(150)
  await viewer.getByRole('button', { name: '축소', exact: true }).click()
  await page.waitForFunction(selector => document.querySelector(selector)?.width === 595, `${scope} .viewer__canvas`)
  await page.waitForTimeout(150)
  const ink = await canvas.evaluate(element => {
    const pixels = element.getContext('2d').getImageData(0, 0, element.width, element.height).data
    let count = 0
    for (let index = 0; index < pixels.length; index += 4) if (pixels[index + 3] && pixels[index] < 200 && pixels[index + 1] < 200 && pixels[index + 2] < 200) count += 1
    return count
  })
  assert.ok(ink > 100, 'The PDF viewer must contain rendered document ink')
  passed('protected single-page PDF renders after explicit viewer zoom', { scope, ink })
}

function assertApplicantProjection(value) {
  if (!value || typeof value !== 'object') return
  for (const [key, child] of Object.entries(value)) {
    assert.ok(!['criteria', 'checklist', 'quote', 'confidence', 'engine_rule', 'source_pages', 'needs_review'].includes(key), `Applicant projection contains ${key}`)
    assertApplicantProjection(child)
  }
}
try {
  assert.deepEqual(await officerJson('/__visual__/identity'), { suite: 'renewal-master-2', synthetic_only: true })
  result.counts_before = await officerJson('/__visual__/counts')
  await officer.goto(`${BASE}/officer/programs/new?mock=0`, { waitUntil: 'domcontentloaded' })
  await officer.getByLabel('담당자 비밀번호').fill('synthetic-visual-password')
  await capture(officer, 'officer-login')
  await officer.getByRole('button', { name: '로그인', exact: true }).click()
  await officer.locator('#program-notice').waitFor({ state: 'attached' })
  await officer.locator('#program-notice').setInputFiles(fixtures.notice)
  await officer.locator('#program-forms').setInputFiles(fixtures.form)
  await officer.locator('#program-supplemental').fill('합성 자료로만 확인하는 공개 안내입니다.')
  await capture(officer, 'officer-one-shot-upload')
  const analyzedResponse = waitResponse(officer, response => response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/officer/programs/analyze')
  await officer.getByRole('button', { name: '분석하기', exact: true }).click()
  const analyzedHttp = await analyzedResponse
  assert.equal(analyzedHttp.status(), 201)
  const analyzed = await analyzedHttp.json()
  const created = analyzed.posting
  assert.ok(created.id)
  result.posting_id = created.id
  await officer.locator('#preview-title-input').waitFor()
  await capture(officer, 'officer-analyzed-preview')
  assert.equal(await officer.getByRole('button', { name: '올리기(게시)', exact: true }).isDisabled(), true)
  const base = `/api/officer/postings/${created.id}`
  assert.equal((await context.request.post(`${BASE}${base}/publish`)).status(), 409)
  assert.equal((await applicantContext.request.get(`${BASE}/api/postings/${created.id}`)).status(), 404)
  passed('unconfirmed analysis and form template cannot publish', 409)
  const fields = Object.values(analyzed.forms[0].layout.fields)
  assert.equal(fields.length, 3)
  await officer.getByRole('button', { name: /^남은 확인/ }).click()
  await officer.getByRole('menuitem', { name: 'Name · 서식', exact: true }).click()
  assert.equal(await officer.getByLabel('라벨', { exact: true }).inputValue(), 'Name')
  passed('pending sidebar selects the matching form field')
  const labels = { Name: ['성명', 'text', 'name'], Message: ['신청 내용', 'text', ''], Signature: ['전자서명', 'signature', ''] }
  for (let index = 0; index < fields.length; index += 1) {
    await officer.locator('.template-editor__field-list button').nth(index).click()
    const expected = labels[fields[index].label]
    assert.ok(expected)
    await officer.getByLabel('라벨', { exact: true }).fill(expected[0])
    await officer.locator('.template-editor__settings select').nth(0).selectOption(expected[1])
    await officer.getByRole('checkbox', { name: '필수 입력', exact: true }).check()
    await officer.locator('.template-editor__settings select').nth(1).selectOption(expected[2])
    await officer.getByRole('button', { name: '이 칸 확인 완료', exact: true }).click()
  }
  await officer.getByRole('button', { name: '서식 확정', exact: true }).click()
  await officer.getByText('틀 확정 완료', { exact: true }).waitFor()
  assert.equal((await context.request.post(`${BASE}${base}/publish`)).status(), 409)
  passed('confirmed form still requires every notice candidate review', 409)
  await officer.locator('#preview-title-input').fill('합성 청년 활동 지원 사업')
  await officer.locator('#preview-guidance-input').fill('합성 청년 활동 지원 사업입니다. 신청 기간 안에 서식을 작성하고 면접용 사진 사본을 올려 주세요. 문의는 합성청년센터로 해 주세요.')
  await officer.getByLabel('신청 시작일', { exact: true }).fill(day)
  await officer.getByLabel('신청 종료일', { exact: true }).fill(endDay)
  let confirmed = 0
  while (await officer.locator('.program-preview__confirm[aria-pressed=false]').count()) {
    assert.ok(confirmed < 30)
    await officer.locator('.program-preview__confirm[aria-pressed=false]').first().click()
    confirmed += 1
  }
  assert.equal(confirmed, 6)
  await capture(officer, 'officer-editable-preview')
  assert.equal(await officer.getByRole('button', { name: '올리기(게시)', exact: true }).isEnabled(), true)
  const publicationRequests = []
  const tracePublication = req => { const path = new URL(req.url()).pathname; if (path === `${base}/analysis` || path === `${base}/workspace` || path === `${base}/publish`) publicationRequests.push(`${req.method()} ${path.split('/').at(-1)}`) }
  officer.on('request', tracePublication)
  const publishResponse = waitResponse(officer, response => response.request().method() === 'POST' && new URL(response.url()).pathname === `${base}/publish`)
  await officer.getByRole('button', { name: '올리기(게시)', exact: true }).click()
  assert.equal((await publishResponse).status(), 200)
  await officer.getByText('사업을 게시했습니다.', { exact: true }).waitFor()
  officer.off('request', tracePublication)
  assert.deepEqual(publicationRequests.slice(0, 3), ['PUT analysis', 'GET workspace', 'POST publish'])
  passed('unsaved reviewed draft publishes through save, fresh blockers, then publish', publicationRequests.slice(0, 3))
  await capture(officer, 'officer-program-published')
  passed('reviewed program published through the preview UI')
  applicant = await applicantContext.newPage(); track(applicant); activePage = applicant
  await applicant.goto(`${BASE}/programs/${created.id}`, { waitUntil: 'networkidle' })
  await applicant.getByRole('button', { name: '신청하기', exact: true }).waitFor()
  await capture(applicant, 'applicant-program-info')
  await applicant.getByRole('button', { name: '신청하기', exact: true }).click()
  await applicant.locator('#identity-name-input').waitFor()
  const identityPath = new URL(applicant.url()).pathname
  for (let visit = 0; visit < 3; visit += 1) {
    await applicant.goto(`${BASE}${identityPath}`, { waitUntil: 'networkidle' })
    await applicant.locator('#identity-name-input').waitFor()
  }
  const beforeSubmit = await applicantJson('/__visual__/counts')
  assert.equal(beforeSubmit.applications, result.counts_before.applications)
  assert.equal(createRequests, 0); passed('three identity visits create zero applications')
  await applicant.locator('#identity-name-input').fill('합성신청')
  for (const [label, value] of [['연도', '2000'], ['월', '1'], ['일', '1']]) await applicant.getByRole('textbox', { name: `생년월일 ${label}`, exact: true }).fill(value)
  await applicant.locator('#identity-phone-input').fill('01012345678')
  await applicant.locator('#identity-pledge input').check()
  await draw(applicant, applicant.locator('.idcheck canvas'))
  await capture(applicant, 'applicant-identity')
  await applicant.getByRole('button', { name: '본인인증 하기', exact: true }).click()
  await applicant.getByRole('dialog').getByRole('button', { name: '본인인증 하기', exact: true }).click()
  await applicant.getByRole('heading', { name: '신청 서식 작성', exact: true }).waitFor()
  const aid = await applicant.evaluate(key => Number(window.sessionStorage.getItem(key)), `applicant.program.${created.id}`)
  assert.ok(aid); result.application_id = aid
  const application = await applicantJson(`/api/applications/${aid}`)
  result.application_no = application.application_no
  await applicant.reload({ waitUntil: 'networkidle' })
  await applicant.getByRole('button', { name: '작성하기', exact: true }).waitFor()
  assert.equal(createRequests, 1)
  const restored = await applicantJson(`/api/applications/${aid}`)
  assert.equal(restored.application_no, result.application_no); passed('identity submit refresh reuses application', result.application_no)
  const outsider = await browser.newContext()
  const unauthorized = await outsider.request.get(`${BASE}/api/applications/${aid}`)
  assert.equal(unauthorized.status(), 403); await outsider.close(); passed('other cookie context cannot read application', 403)
  await applicant.getByRole('button', { name: '작성하기', exact: true }).click()
  await applicant.getByRole('textbox', { name: '신청 내용', exact: true }).fill('지역 활동 참여를 위한 합성 신청입니다.')
  assert.equal(await applicant.getByRole('textbox', { name: '성명', exact: true }).isEditable(), false)
  await applicant.locator('.pdf-form__sign').click()
  await draw(applicant, applicant.locator('.pdf-form__sign-pad canvas'))
  await applicant.getByRole('button', { name: '서명 입력 마치기', exact: true }).click()
  const backgrounds = applicant.locator('.pdf-form__background')
  assert.equal(await backgrounds.evaluateAll(images => images.every(image => image.complete && image.naturalWidth > 0)), true)
  passed('owner cookie renders actual form image and locks identity autofill')
  assert.equal(await applicant.getByRole('heading', { name: '지원 자격 확인', exact: true }).count(), 0)
  assert.equal(await applicant.getByRole('heading', { name: '입금 받을 계좌', exact: true }).count(), 0)
  await capture(applicant, 'applicant-forms')
  await applicant.getByRole('button', { name: '저장하고 닫기', exact: true }).click()
  await applicant.getByRole('button', { name: '서류 업로드로', exact: true }).click()
  await applicant.getByRole('heading', { name: '서류 업로드', exact: true }).waitFor()
  const uploadedResponse = waitResponse(applicant, response => response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith('/documents'))
  await applicant.locator('#slot-photo_1_photo input[type=file]').setInputFiles(fixtures.image)
  const uploaded = await (await uploadedResponse).json()
  assert.equal(uploaded.status, 'NEEDS_REVIEW'); passed('unknown high-resolution synthetic image stays NEEDS_REVIEW')
  await applicant.locator('.dresult').waitFor()
  assert.equal(await applicant.getByRole('button', { name: '최종 확인으로', exact: true }).isEnabled(), true)
  const original = await applicantContext.request.get(`${BASE}${uploaded.file_url}`)
  assert.equal(original.status(), 200)
  assert.ok((original.headers()['content-disposition'] ?? '').startsWith('inline')); passed('owner original preview remains inline')
  await capture(applicant, 'applicant-upload')
  await applicant.getByRole('button', { name: '최종 확인으로', exact: true }).click()
  await applicant.getByRole('heading', { name: '확인 및 제출', exact: true }).waitFor()
  const final = await applicantJson(`/api/applications/${aid}/final-check`)
  assert.equal(final.can_submit, true); assert.equal(final.blockers.length, 0); assert.equal(final.selection, 'manual')
  await capture(applicant, 'applicant-final')
  await applicant.getByRole('button', { name: '제출하기', exact: true }).click()
  await applicant.getByRole('dialog').getByRole('button', { name: '제출하기', exact: true }).click()
  await applicant.getByRole('heading', { name: '신청이 접수되었습니다', exact: true }).waitFor()
  await capture(applicant, 'applicant-receipt')
  const archive = await applicantContext.request.get(`${BASE}/api/applications/${aid}/forms/files/written.pdf`)
  const archiveBytes = await archive.body()
  assert.equal(archive.status(), 200); assert.ok(archiveBytes.subarray(0, 5).equals(Buffer.from('%PDF-')))
  passed('submission generates owner-readable written PDF archive')
  const blockedDelete = await applicantContext.request.delete(`${BASE}/api/applications/${aid}/documents/${uploaded.document_id}`)
  assert.equal(blockedDelete.status(), 409)
  const archiveAfterDelete = await applicantContext.request.get(`${BASE}/api/applications/${aid}/forms/files/written.pdf`)
  assert.equal(archiveAfterDelete.status(), 200); assert.ok((await archiveAfterDelete.body()).equals(archiveBytes))
  passed('submitted generic document deletion blocked and archive unchanged', 409)
  const blockedUpload = await applicantContext.request.post(`${BASE}/api/applications/${aid}/documents`, { multipart: {
    slot_key: 'photo_1_photo', file: { name: 'visual-upload.png', mimeType: 'image/png', buffer: await readFile(fixtures.image) },
  } })
  assert.equal(blockedUpload.status(), 409)
  const archiveAfterUpload = await applicantContext.request.get(`${BASE}/api/applications/${aid}/forms/files/written.pdf`)
  assert.equal(archiveAfterUpload.status(), 200); assert.ok((await archiveAfterUpload.body()).equals(archiveBytes))
  passed('submitted generic document reupload blocked and archive unchanged', 409)
  await applicant.locator('#main').getByRole('button', { name: '마이페이지', exact: true }).click()
  await applicant.locator('.mypage__head').waitFor()
  await capture(applicant, 'applicant-mypage')

  activePage = officer
  await officer.goto(`${BASE}/officer/programs/${created.id}?mock=0`, { waitUntil: 'networkidle' })
  await officer.locator('.managed-program__applications').waitFor()
  const listing = await officerJson(`/api/officer/applications?role=province&program=posting_${created.id}&queue=needs_check`)
  assert.equal(listing.total, 1)
  assert.equal(listing.rows[0].application_no, result.application_no)
  await capture(officer, 'officer-program-applications')
  const genericPath = `/api/officer/programs/${created.id}/applications/${aid}`
  assert.equal((await context.request.post(`${BASE}${genericPath}/decision`, { data: { role: 'province', decision: 'approve', memo: '' } })).status(), 409)
  assert.equal((await context.request.post(`${BASE}/api/officer/applications/decisions`, { data: { role: 'province', decision: 'approve', memo: '', application_ids: [aid] } })).status(), 409)
  passed('unchecked individual and bulk final selection both rejected', 409)
  await officer.locator('.alist__open').first().click()
  await officer.locator('.generic-review').waitFor()
  await officer.locator('.generic-review .viewer__image').waitFor()
  assert.equal(await officer.getByRole('heading', { name: /심사표/ }).count(), 0)
  const detail = await officerJson(genericPath)
  assert.equal(detail.documents.length, 2)
  assert.equal(detail.criteria.filter(item => item.requires_check).length, 1)
  assert.ok(detail.criteria.some(item => item.type === 'age' && item.result === 'PASS'))
  assert.ok(detail.criteria.some(item => item.type === 'checklist' && item.requires_check))
  assert.equal(detail.ai.final_status, 'NEEDS_REVIEW')
  assert.equal(await officer.getByRole('button', { name: '최종 선정', exact: true }).isDisabled(), true)
  await capture(officer, 'officer-generic-review-detail')
  const writtenDocument = detail.documents.find(item => item.slot_key === 'written')
  assert.equal(writtenDocument.file_format, 'pdf')
  assert.ok(writtenDocument.page_image_url)
  await officer.getByRole('tab', { name: '작성한 서식', exact: true }).click()
  await officer.waitForFunction(expected => {
    const image = document.querySelector('.generic-review .viewer__image')
    return image?.getAttribute('src') === expected && image.complete && image.naturalWidth > 0
  }, writtenDocument.page_image_url)
  const rendered = await officer.locator('.generic-review .viewer__image').evaluate(image => ({ width: image.naturalWidth, height: image.naturalHeight }))
  const originalAfterPreview = await context.request.get(`${BASE}${writtenDocument.file_url}`)
  assert.equal(originalAfterPreview.status(), 200)
  assert.ok(archiveBytes.equals(await originalAfterPreview.body()))
  result.raster_check = { rendered, page_image_url: writtenDocument.page_image_url, source_file_format: 'pdf', original_bytes_unchanged: true, zoom_actions: 0 }
  passed('generic written original renders on first paint without viewer zoom', result.raster_check)
  await capture(officer, 'officer-generic-written-form')
  const checks = officer.locator('.generic-review').getByRole('checkbox')
  assert.equal(await checks.count(), 3)
  for (let index = 0; index < 3; index += 1) {
    const checkedResponse = waitResponse(officer, response => response.request().method() === 'PUT' && new URL(response.url()).pathname === `${genericPath}/checks`)
    await checks.nth(index).click()
    assert.equal((await checkedResponse).status(), 200)
    await officer.waitForFunction(position => document.querySelectorAll('.generic-review input[type=checkbox]')[position]?.checked === true, index)
  }
  const chosenResponse = waitResponse(officer, response => response.request().method() === 'POST' && new URL(response.url()).pathname === `${genericPath}/decision`)
  await officer.getByRole('button', { name: '최종 선정', exact: true }).click()
  const chosen = await (await chosenResponse).json()
  assert.equal(chosen.status, 'decided')
  assert.equal(chosen.decision.decision, 'approve')
  await capture(officer, 'officer-generic-final-selection')
  passed('all original and checklist confirmations permit final selection', 3)

  const publicPosting = await applicantJson(`/api/postings/${created.id}`)
  const publicProgram = await applicantJson(`/api/applications/${aid}/program`)
  const publicForms = await applicantJson(`/api/applications/${aid}/forms`)
  const publicLayout = await applicantJson(`/api/applications/${aid}/forms/layouts/${publicForms[0].form_no}`)
  assertApplicantProjection(publicPosting)
  assertApplicantProjection(publicProgram)
  assertApplicantProjection(publicLayout)
  passed('applicant metadata and form layouts exclude internal analysis evidence')

  result.counts_after = await officerJson('/__visual__/counts')
  assert.equal(result.counts_after.applications, result.counts_before.applications + 1)
  assert.equal(createRequests, 1)
  assert.equal(result.page_errors.length, 0, JSON.stringify(result.page_errors))
  console.log(JSON.stringify({ assertions: result.assertions.length, page_errors: result.page_errors }))
} catch (error) {
  result.errors.push(clean(error))
  await activePage.screenshot({ path: `${SHOTS}/e2e-failure.png`, fullPage: true }).catch(() => undefined)
  console.error(clean(error))
  process.exitCode = 1
} finally {
  await writeFile(new URL('./visual-e2e-result.json', OUTPUT), JSON.stringify(result, null, 2) + '\n')
  await browser.close()
}
