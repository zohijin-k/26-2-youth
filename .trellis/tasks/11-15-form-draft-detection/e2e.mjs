/** Loopback UI journey: upload public blank templates, check auto fields, snap one, confirm, publish, apply. */
const { chromium } = await import(process.env.PLAYWRIGHT_PACKAGE ?? '/tmp/renewal-npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright/index.mjs')
import assert from 'node:assert/strict'
import { writeFile, mkdir } from 'node:fs/promises'

const BASE = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:5191'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(BASE).hostname))
const FILES = '/tmp/form-draft-detection-e2e/files'
const SHOTS = new URL('./shots/', import.meta.url).pathname.replace(/\/$/, '')
const SNAP = JSON.parse(process.env.E2E_SNAP_POINT ?? '{"x":300,"y":100}')
await mkdir(SHOTS, { recursive: true })
const result = { forms: [], snap: null, security: [], assertions: [], shots: [], page_errors: [], request_failures: [], stage: 'start' }
const browser = await chromium.launch({ headless: true })
const options = { deviceScaleFactor: 1, locale: 'ko-KR', timezoneId: 'Asia/Seoul', reducedMotion: 'reduce' }
const context = await browser.newContext({ ...options, viewport: { width: 1440, height: 1100 } })
const applicantContext = await browser.newContext({ ...options, viewport: { width: 940, height: 1000 } })
const officer = await context.newPage()
let applicant
track(officer)
function track(page) {
  page.on('pageerror', error => result.page_errors.push(String(error).slice(0, 200)))
  page.on('requestfailed', request => result.request_failures.push(new URL(request.url()).pathname))
  page.on('request', request => {
    const url = new URL(request.url())
    if (['http:', 'https:'].includes(url.protocol)) assert.ok(['127.0.0.1', 'localhost'].includes(url.hostname), 'External request is forbidden')
  })
}
function passed(name, detail = 'O') { result.assertions.push({ name, detail }); console.log('O ' + name + ' ' + JSON.stringify(detail)) }
async function capture(page, name) {
  result.stage = name
  await page.evaluate(async () => {
    await document.fonts.ready
    await Promise.all([...document.images].map(image => image.decode().catch(() => undefined)))
  })
  const path = `${SHOTS}/${name}.png`
  await page.screenshot({ path, fullPage: true, animations: 'disabled' })
  result.shots.push({ name, path })
}
async function draw(page, canvas) {
  await canvas.scrollIntoViewIfNeeded()
  const box = await canvas.boundingBox()
  await page.mouse.move(box.x + 20, box.y + 20)
  await page.mouse.down()
  await page.mouse.move(box.x + Math.min(110, box.width - 20), box.y + Math.min(55, box.height - 15), { steps: 10 })
  await page.mouse.move(box.x + Math.min(140, box.width - 10), box.y + 28, { steps: 6 })
  await page.mouse.up()
}
const waitResponse = (page, predicate) => { const pending = page.waitForResponse(predicate); void pending.catch(() => undefined); return pending }
const editor = () => officer.locator('.template-editor')

try {
  await officer.goto(`${BASE}/officer/programs/new?mock=0`, { waitUntil: 'domcontentloaded' })
  await officer.getByLabel('담당자 비밀번호').fill('synthetic-e2e-password')
  await officer.getByRole('button', { name: '로그인', exact: true }).click()
  await officer.locator('#program-notice').waitFor({ state: 'attached' })
  await officer.locator('#program-notice').setInputFiles(`${FILES}/notice.pdf`)
  await officer.locator('#program-forms').setInputFiles([`${FILES}/form2-self-check.pdf`, `${FILES}/form5-consent.pdf`])
  await capture(officer, '01-officer-upload')
  const analyzedResponse = waitResponse(officer, response => response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/officer/programs/analyze')
  await officer.getByRole('button', { name: '분석하기', exact: true }).click()
  const analyzedHttp = await analyzedResponse
  assert.equal(analyzedHttp.status(), 201)
  const analyzed = await analyzedHttp.json()
  const postingId = analyzed.posting.id
  const base = `/api/officer/postings/${postingId}`
  for (const form of analyzed.forms) {
    const fields = Object.values(form.layout.fields)
    const kinds = {}
    for (const field of fields) kinds[field.field_type] = (kinds[field.field_type] ?? 0) + 1
    result.forms.push({ form_id: form.id, auto_fields: fields.length, kinds, all_need_review: fields.every(field => field.needs_review), confirmed: form.confirmed })
    assert.ok(fields.length > 0 && fields.every(field => field.needs_review) && !form.confirmed)
  }
  passed('uploaded templates drafted with every field needing review', result.forms.map(form => form.auto_fields))
  await officer.locator('#preview-title-input').waitFor()
  await editor().scrollIntoViewIfNeeded()
  await officer.locator('.template-editor__page img').waitFor()
  await capture(officer, '02-officer-auto-fields-form2')

  // Security probes for the snap route: no cookie → 401, officer → 200.
  const formId = analyzed.forms[0].id
  const snapPath = `${base}/workspace/forms/${formId}/snap`
  const anonymous = await browser.newContext()
  const denied = await anonymous.request.post(`${BASE}${snapPath}`, { data: { page: 0, ...SNAP } })
  await anonymous.close()
  const allowed = await context.request.post(`${BASE}${snapPath}`, { data: { page: 0, ...SNAP } })
  result.security.push({ method: 'POST', path: '/api/officer/postings/{id}/workspace/forms/{form_id}/snap', no_cookie: denied.status(), officer: allowed.status() })
  assert.equal(denied.status(), 401); assert.equal(allowed.status(), 200)
  passed('snap route: no cookie 401, officer 200', [denied.status(), allowed.status()])

  // Click (not drag) with "칸 추가" on the first form's page.
  const before = await officer.locator('.template-editor__field-list li').count()
  await editor().getByRole('button', { name: '칸 추가', exact: true }).click()
  const canvas = officer.locator('.template-editor__page')
  const box = await canvas.boundingBox()
  const size = analyzed.forms[0].layout.page_sizes[0]
  const snapResponse = waitResponse(officer, response => new URL(response.url()).pathname === snapPath)
  await officer.mouse.click(box.x + SNAP.x / size.width * box.width, box.y + SNAP.y / size.height * box.height)
  const snapped = await (await snapResponse).json()
  await officer.waitForFunction(count => document.querySelectorAll('.template-editor__field-list li').length === count + 1, before)
  const label = await officer.getByLabel('라벨', { exact: true }).inputValue()
  result.snap = { point: SNAP, box: snapped.box, field_type: snapped.field_type ?? null, editor_label: label }
  assert.ok(snapped.box, 'snap returned a box')
  passed('add-field click snapped to a nearby cell/blank', result.snap)
  await capture(officer, '03-officer-snapped-field')

  // Review every field of every form, then confirm each form.
  for (let index = 0; index < analyzed.forms.length; index += 1) {
    if (index) {
      await editor().locator('.template-editor__toolbar select').first().selectOption(String(analyzed.forms[index].id))
      await officer.locator('.template-editor__page img').waitFor()
    }
    let reviewed = 0
    for (;;) {
      const pending = editor().locator('.template-editor__field-list button', { hasText: '△' })
      if (!(await pending.count())) break
      assert.ok(reviewed < 60)
      await pending.first().click()
      await editor().getByRole('button', { name: '이 칸 확인 완료', exact: true }).click()
      reviewed += 1
    }
    const confirmResponse = waitResponse(officer, response => response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith(`/forms/${analyzed.forms[index].id}/confirm`))
    await editor().getByRole('button', { name: '서식 확정', exact: true }).click()
    assert.equal((await confirmResponse).status(), 200)
    passed(`form ${index + 1} reviewed and confirmed`, reviewed)
    if (index === analyzed.forms.length - 1) await capture(officer, '04-officer-form5-confirmed')
  }

  await officer.locator('#preview-title-input').fill('합성 청년 서식 확인 사업')
  await officer.locator('#preview-guidance-input').fill('합성 서식 확인 사업입니다. 신청 기간 안에 서식을 작성하고 면접용 사진 사본을 올려 주세요. 문의는 합성청년센터로 해 주세요.')
  await officer.getByLabel('신청 시작일', { exact: true }).fill('2026-11-15')
  await officer.getByLabel('신청 종료일', { exact: true }).fill('2026-12-31')
  let confirmations = 0
  for (;;) {
    const button = officer.locator('button.program-preview__confirm:not([disabled])')
    if (!(await button.count())) break
    assert.ok(confirmations < 30)
    await button.first().click()
    confirmations += 1
  }
  passed('notice items confirmed', confirmations)
  const publishResponse = waitResponse(officer, response => response.request().method() === 'POST' && new URL(response.url()).pathname === `${base}/publish`)
  await officer.getByRole('button', { name: '올리기(게시)', exact: true }).click()
  assert.equal((await publishResponse).status(), 200)
  await capture(officer, '05-officer-published')
  passed('program published')

  applicant = await applicantContext.newPage(); track(applicant)
  await applicant.goto(`${BASE}/programs/${postingId}`, { waitUntil: 'networkidle' })
  await applicant.getByRole('button', { name: '신청하기', exact: true }).click()
  await applicant.locator('#identity-name-input').fill('합성신청')
  for (const [part, value] of [['연도', '2000'], ['월', '1'], ['일', '1']]) await applicant.getByRole('textbox', { name: `생년월일 ${part}`, exact: true }).fill(value)
  await applicant.locator('#identity-phone-input').fill('01012345678')
  await applicant.locator('#identity-pledge input').check()
  await draw(applicant, applicant.locator('.idcheck canvas'))
  await applicant.getByRole('button', { name: '본인인증 하기', exact: true }).click()
  await applicant.getByRole('dialog').getByRole('button', { name: '본인인증 하기', exact: true }).click()
  await applicant.getByRole('heading', { name: '신청 서식 작성', exact: true }).waitFor()
  const writeButtons = applicant.getByRole('button', { name: /^(작성하기|수정)$/ })
  await writeButtons.first().waitFor()
  const formCount = await writeButtons.count()
  for (let index = 0; index < formCount; index += 1) {
    await applicant.getByRole('button', { name: /^(작성하기|수정)$/ }).nth(index).click()
    await applicant.locator('.pdf-form__background').first().waitFor()
    const checks = applicant.locator('label.pdf-form__check')
    const checkCount = await checks.count()
    let ticked = 0
    for (let at = 0; at < checkCount; at += 2) {
      await checks.nth(at).click()
      if (await checks.nth(at).locator('input').isChecked()) ticked += 1
    }
    const signs = applicant.locator('.pdf-form__sign')
    if (await signs.count()) {
      await signs.first().click()
      await draw(applicant, applicant.locator('.pdf-form__sign-pad canvas'))
      await applicant.getByRole('button', { name: '서명 입력 마치기', exact: true }).click()
    }
    await capture(applicant, `0${6 + index}-applicant-form-${index + 1}`)
    passed(`applicant filled form ${index + 1}`, { check_fields: checkCount, checks_ticked: ticked, signatures: await signs.count() })
    await applicant.getByRole('button', { name: '저장하고 닫기', exact: true }).click()
  }
  await applicant.getByRole('button', { name: '서류 업로드로', exact: true }).click()
  await applicant.getByRole('heading', { name: '서류 업로드', exact: true }).waitFor()
  const uploadInput = applicant.locator('input[type=file]').first()
  await uploadInput.setInputFiles(`${FILES}/upload.png`)
  await applicant.locator('.dresult').first().waitFor()
  await applicant.getByRole('button', { name: '최종 확인으로', exact: true }).click()
  await applicant.getByRole('heading', { name: '확인 및 제출', exact: true }).waitFor()
  await capture(applicant, '08-applicant-final')
  await applicant.getByRole('button', { name: '제출하기', exact: true }).click()
  await applicant.getByRole('dialog').getByRole('button', { name: '제출하기', exact: true }).click()
  await applicant.getByRole('heading', { name: '신청이 접수되었습니다', exact: true }).waitFor()
  await capture(applicant, '09-applicant-receipt')
  passed('applicant submitted')
  result.result = 'passed'
} catch (error) {
  result.result = 'failed'
  result.error = String(error).slice(0, 400)
  const page = applicant ?? officer
  await page.screenshot({ path: `${SHOTS}/failure.png`, fullPage: true }).catch(() => undefined)
} finally {
  await writeFile(new URL('./e2e-result.json', import.meta.url), JSON.stringify(result, null, 2) + '\n')
  await browser.close()
}
console.log(result.result, result.error ?? '')
process.exit(result.result === 'passed' ? 0 : 1)
