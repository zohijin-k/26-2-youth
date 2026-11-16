/** Loopback check of the officer program fixes against e2e_backend.py (fake provider, temp DB).
 * Screenshots and assertions go to SHOTS (env) — results JSON lists every assertion. */
const { chromium } = await import(process.env.PLAYWRIGHT_PACKAGE)
import assert from 'node:assert/strict'
import { writeFile, mkdir } from 'node:fs/promises'

const BASE = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:5193'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(BASE).hostname))
const FILES = `${process.env.E2E_ROOT}/files`
const SHOTS = process.env.SHOTS
await mkdir(SHOTS, { recursive: true })
const result = { assertions: [], page_errors: [] }
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ deviceScaleFactor: 1, locale: 'ko-KR', timezoneId: 'Asia/Seoul', reducedMotion: 'reduce', viewport: { width: 1440, height: 1100 } })
const page = await context.newPage()
page.on('pageerror', error => result.page_errors.push(String(error).slice(0, 200)))
page.on('request', request => {
  const url = new URL(request.url())
  if (['http:', 'https:'].includes(url.protocol)) assert.ok(['127.0.0.1', 'localhost'].includes(url.hostname), 'External request is forbidden')
})
const passed = (name, detail = 'O') => { result.assertions.push({ name, detail }); console.log('O ' + name + ' ' + JSON.stringify(detail)) }

async function analyze() {
  await page.goto(`${BASE}/officer/programs/new?mock=0`, { waitUntil: 'domcontentloaded' })
  const login = page.getByLabel('담당자 비밀번호')
  await login.or(page.locator('#program-notice')).first().waitFor({ state: 'attached' })
  if (await login.count()) {
    await login.fill('synthetic-e2e-password')
    await page.getByRole('button', { name: '로그인', exact: true }).click()
  }
  await page.locator('#program-notice').waitFor({ state: 'attached' })
  await page.locator('#program-notice').setInputFiles(`${FILES}/notice.pdf`)
  await page.locator('#program-forms').setInputFiles([`${FILES}/form.pdf`])
  const analyzed = page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/officer/programs/analyze')
  await page.getByRole('button', { name: '분석하기', exact: true }).click()
  const response = await analyzed
  assert.equal(response.status(), 201)
  await page.locator('#preview-title-input').waitFor()
  return response.json()
}

try {
  const data = await analyze()
  // 4·5: guidance written from the overview lands in the field, line breaks become paragraphs.
  const textarea = page.locator('#preview-guidance-input')
  assert.equal((await textarea.inputValue()).split('\n').length, 6)
  const guidance = page.locator('#preview-guidance')
  assert.equal(await guidance.locator('.om-chip').first().innerText(), 'AI 작성 · 공고문과 대조 필요')
  const paragraphs = guidance.locator('.pinfo__guidance p')
  assert.equal(await paragraphs.count(), 6)
  passed('AI guidance fills the field and preview shows one paragraph per line', 6)
  await textarea.fill(`${await textarea.inputValue()}\n직접 입력한 새 문단입니다.`)
  await page.waitForFunction(() => document.querySelectorAll('#preview-guidance .pinfo__guidance p').length === 7)
  assert.equal(await paragraphs.count(), 7)
  assert.equal(await paragraphs.nth(6).innerText(), '직접 입력한 새 문단입니다.')
  assert.equal(await guidance.locator('.om-chip').count(), 0)
  passed('typing a line break adds a preview paragraph; edited guidance drops the AI chip')
  await guidance.screenshot({ path: `${SHOTS}/guidance.png`, animations: 'disabled' })

  // 6·7: document groups and separate criteria section.
  const docs = page.locator('#preview-documents')
  assert.equal(await docs.locator('h2').innerText(), '④ 업로드 서류')
  assert.deepEqual(await docs.locator('h3').allInnerTexts(), ['필수 업로드 서류', '추가 업로드 서류'])
  const text = await docs.innerText()
  assert.ok(!text.includes('지정 서류') && !text.includes('기타 서류'), 'old jargon is gone')
  assert.equal(await page.locator('#preview-criteria h2').innerText(), '⑤ 신청 자격 기준')
  passed('documents split into required/additional groups; criteria in their own section')
  await docs.getByRole('button', { name: '추가 서류 추가' }).click()
  const added = docs.locator('.program-preview__docs-group').nth(1).locator('article').last()
  await added.getByLabel('서류 이름').fill('수상 실적 증빙')
  // 3: a manual item shows neither the "근거 없음·직접 입력" chip nor the source toggle; button reads 작성완료.
  assert.equal(await added.getByRole('button', { name: '근거', exact: true }).count(), 0)
  assert.ok(!(await added.innerText()).includes('근거 없음'))
  assert.equal(await added.locator('.program-preview__confirm').innerText(), '□ 작성완료')
  await added.locator('.program-preview__confirm').click()
  assert.equal(await added.locator('.program-preview__confirm').innerText(), '✓ 작성완료')
  passed('manual item: no 근거 chip/toggle, confirm reads 작성완료')
  await docs.screenshot({ path: `${SHOTS}/documents.png`, animations: 'disabled' })
  await page.locator('#preview-criteria').screenshot({ path: `${SHOTS}/criteria.png`, animations: 'disabled' })
  await page.screenshot({ path: `${SHOTS}/editor-top.png`, animations: 'disabled' })

  // 2: a published program shows a visible 수정하기 button that unpublishes after confirmation.
  const id = data.posting.id
  const forced = await page.request.post(`${BASE}/api/__e2e/force-publish/${id}`)
  assert.equal(forced.status(), 200)
  page.once('dialog', dialog => dialog.accept())
  await page.reload({ waitUntil: 'domcontentloaded' })
  const edit = page.getByRole('button', { name: '수정하기', exact: true })
  await edit.waitFor()
  assert.equal(await page.getByRole('button', { name: '올리기(게시)' }).count(), 0)
  await page.locator('.program-preview__bar').screenshot({ path: `${SHOTS}/published-bar.png`, animations: 'disabled' })
  await edit.click()
  await page.getByRole('button', { name: '게시 내리고 수정', exact: true }).click()
  await page.getByText('수정할 수 있도록 게시를 내렸습니다.', { exact: false }).waitFor()
  await page.waitForFunction(() => !document.querySelector('#preview-title-input')?.disabled, null, { timeout: 10000 })
  assert.equal(await page.getByRole('button', { name: '올리기(게시)' }).count(), 1)
  passed('published program: 수정하기 unpublishes and re-enables editing')

  // 1: delete from the editor menu, then from the list menu.
  await page.getByRole('button', { name: '사업 더보기' }).click()
  await page.getByRole('menuitem', { name: '사업 삭제' }).click()
  await page.getByRole('button', { name: '삭제', exact: true }).click()
  await page.locator('.plist__title').waitFor()
  assert.equal((await page.request.get(`${BASE}/api/officer/postings/${id}`)).status(), 404)
  passed('editor menu deletes the program and returns to the list')

  const second = await analyze()
  await page.request.post(`${BASE}/api/__e2e/force-publish/${second.posting.id}`)
  await page.goto(`${BASE}/officer/programs?mock=0`, { waitUntil: 'domcontentloaded' })
  await page.locator('.plist__title').waitFor()
  const card = page.locator('.om-program-card', { has: page.locator(`a[href*="/officer/programs/${second.posting.id}"]`) })
  result.list_cards_before = await page.locator('.om-program-card').count()
  await card.getByRole('button', { name: `${second.posting.title} 더보기` }).click()
  await page.screenshot({ path: `${SHOTS}/list-menu.png`, animations: 'disabled' })
  await page.getByRole('menuitem', { name: '사업 삭제' }).click()
  await page.getByRole('button', { name: '삭제', exact: true }).click()
  await page.getByText('사업을 지웠습니다.', { exact: false }).waitFor()
  assert.equal(await card.count(), 0)
  passed('list menu deletes a published program')

  assert.deepEqual(result.page_errors, [])
  passed('no page errors')
  result.result = 'passed'
} catch (error) {
  result.result = 'failed'
  result.error = String(error).slice(0, 500)
  await page.screenshot({ path: `${SHOTS}/failure.png` }).catch(() => {})
  process.exitCode = 1
} finally {
  await writeFile(`${SHOTS}/e2e-result.json`, JSON.stringify(result, null, 2) + '\n')
  await browser.close()
}
