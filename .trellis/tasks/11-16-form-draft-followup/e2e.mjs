/** Loopback UI journey: officer uploads 서식2·서식5 (English file names), checks auto fields, confirms,
 * publishes; applicant picks one choice word, switches to the other, submits; the submitted PDF is saved
 * for the ○ check (e2e_submitted.py). E2E_MODE names the code under test: committed | stage1-patch. */
const { chromium } = await import(process.env.PLAYWRIGHT_PACKAGE ?? '/tmp/renewal-npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright/index.mjs')
import assert from 'node:assert/strict'
import { writeFile, mkdir } from 'node:fs/promises'

const MODE = process.env.E2E_MODE ?? 'committed'
assert.ok(['committed', 'stage1-patch'].includes(MODE))
const BASE = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:5191'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(BASE).hostname))
const FILES = '/tmp/form-draft-followup-e2e/files'
const SHOTS = new URL('./shots/', import.meta.url).pathname.replace(/\/$/, '')
await mkdir(SHOTS, { recursive: true })
const result = { mode: MODE, forms: [], choice: null, assertions: [], shots: [], page_errors: [], request_failures: [], stage: 'start' }
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
  const path = `${SHOTS}/${MODE}-${name}.png`
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
    result.forms.push({ form_id: form.id, auto_fields: fields.length, kinds, circle_marks: fields.filter(field => field.choice_mark === 'circle').length,
      all_need_review: fields.every(field => field.needs_review), confirmed: form.confirmed })
    assert.ok(fields.length > 0 && fields.every(field => field.needs_review) && !form.confirmed)
  }
  passed('uploaded templates drafted with every field needing review', result.forms.map(form => [form.auto_fields, form.kinds, form.circle_marks]))
  await officer.locator('#preview-title-input').waitFor()
  await editor().scrollIntoViewIfNeeded()
  await officer.locator('.template-editor__page img').waitFor()
  await capture(officer, '01-officer-auto-fields-form2')

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
  }
  await capture(officer, '02-officer-forms-confirmed')

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
  const publishResponse = waitResponse(officer, response => response.request().method() === 'POST' && new URL(response.url()).pathname === `${base}/publish`)
  await officer.getByRole('button', { name: '올리기(게시)', exact: true }).click()
  assert.equal((await publishResponse).status(), 200)
  await capture(officer, '03-officer-published')
  passed('program published', confirmations)

  applicant = await applicantContext.newPage(); track(applicant)
  let applicationId = null
  applicant.on('response', async response => {
    const url = new URL(response.url())
    if (response.request().method() === 'POST' && url.pathname === '/api/applications' && response.ok()) applicationId = (await response.json()).id
  })
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
  assert.ok(applicationId, 'application id seen')
  const writeButtons = applicant.getByRole('button', { name: /^(작성하기|수정)$/ })
  await writeButtons.first().waitFor()
  const formCount = await writeButtons.count()
  for (let index = 0; index < formCount; index += 1) {
    await applicant.getByRole('button', { name: /^(작성하기|수정)$/ }).nth(index).click()
    await applicant.locator('.pdf-form__background').first().waitFor()
    const checks = applicant.locator('label.pdf-form__check')
    const checkCount = await checks.count()
    if (index === 0) {
      // Row 1: pick the first word, then switch to the second; record both states each time.
      const states = async () => [await checks.nth(0).locator('input').isChecked(), await checks.nth(1).locator('input').isChecked()]
      await checks.nth(0).click()
      const first = await states()
      const circlesFirst = await applicant.locator('[data-choice-mark="circle"]').count()
      await capture(applicant, '04-applicant-picked-first')
      await checks.nth(1).click()
      const switched = await states()
      const circlesSwitched = await applicant.locator('[data-choice-mark="circle"]').count()
      await capture(applicant, '05-applicant-switched')
      result.choice = { input_type: await checks.nth(0).locator('input').getAttribute('type'), after_first: first, after_switch: switched,
        circles_after_first: circlesFirst, circles_after_switch: circlesSwitched }
      passed('choice row 1: pick then switch', result.choice)
      for (let at = 2; at < checkCount; at += 2) await checks.nth(at).click()
    } else {
      for (let at = 0; at < checkCount; at += 2) await checks.nth(at).click()
    }
    const signs = applicant.locator('.pdf-form__sign')
    if (await signs.count()) {
      await signs.first().click()
      await draw(applicant, applicant.locator('.pdf-form__sign-pad canvas'))
      await applicant.getByRole('button', { name: '서명 입력 마치기', exact: true }).click()
    }
    if (index) await capture(applicant, `0${5 + index}-applicant-form-${index + 1}`)
    passed(`applicant filled form ${index + 1}`, { check_fields: checkCount, signatures: await signs.count() })
    await applicant.getByRole('button', { name: '저장하고 닫기', exact: true }).click()
  }
  await applicant.getByRole('button', { name: '서류 업로드로', exact: true }).click()
  await applicant.getByRole('heading', { name: '서류 업로드', exact: true }).waitFor()
  await applicant.locator('input[type=file]').first().setInputFiles(`${FILES}/upload.png`)
  await applicant.locator('.dresult').first().waitFor()
  await applicant.getByRole('button', { name: '최종 확인으로', exact: true }).click()
  await applicant.getByRole('heading', { name: '확인 및 제출', exact: true }).waitFor()
  await applicant.getByRole('button', { name: '제출하기', exact: true }).click()
  await applicant.getByRole('dialog').getByRole('button', { name: '제출하기', exact: true }).click()
  await applicant.getByRole('heading', { name: '신청이 접수되었습니다', exact: true }).waitFor()
  await capture(applicant, '07-applicant-receipt')
  passed('applicant submitted')
  const written = await applicantContext.request.get(`${BASE}/api/applications/${applicationId}/forms/files/written.pdf`)
  assert.equal(written.status(), 200)
  await writeFile(`/tmp/form-draft-followup-e2e/submitted-${MODE}.pdf`, await written.body())
  passed('submitted PDF saved for the circle check', `submitted-${MODE}.pdf`)
  result.result = 'passed'
} catch (error) {
  result.result = 'failed'
  result.error = String(error).slice(0, 400)
  const page = applicant ?? officer
  await page.screenshot({ path: `${SHOTS}/${MODE}-failure.png`, fullPage: true }).catch(() => undefined)
} finally {
  await writeFile(new URL(`./e2e-result-${MODE}.json`, import.meta.url), JSON.stringify(result, null, 2) + '\n')
  await browser.close()
}
console.log(result.result, result.error ?? '')
process.exit(result.result === 'passed' ? 0 : 1)
