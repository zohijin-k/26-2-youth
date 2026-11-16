/** Loopback check of list sorting and the reject page against e2e_backend.py (seeded temp DB, mock=0). */
const { chromium } = await import(process.env.PLAYWRIGHT_PACKAGE)
import assert from 'node:assert/strict'
import { writeFile, mkdir } from 'node:fs/promises'

const BASE = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:5194'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(BASE).hostname))
const SHOTS = process.env.SHOTS
await mkdir(SHOTS, { recursive: true })
const result = { assertions: [], page_errors: [] }
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ deviceScaleFactor: 1, locale: 'ko-KR', timezoneId: 'Asia/Seoul', reducedMotion: 'reduce', viewport: { width: 1440, height: 1000 } })
const page = await context.newPage()
page.on('pageerror', error => result.page_errors.push(String(error).slice(0, 200)))
page.on('request', request => {
  const url = new URL(request.url())
  if (['http:', 'https:'].includes(url.protocol)) assert.ok(['127.0.0.1', 'localhost'].includes(url.hostname), 'External request is forbidden')
})
const passed = (name, detail = 'O') => { result.assertions.push({ name, detail }); console.log('O ' + name + ' ' + JSON.stringify(detail)) }
const numbers = () => page.locator('.alist__row .alist__open').allInnerTexts()
const waitNumbers = async (expected) => {
  await page.waitForFunction((want) => JSON.stringify([...document.querySelectorAll('.alist__row .alist__open')].map((el) => el.textContent.trim())) === JSON.stringify(want), expected, { timeout: 10000 })
}

try {
  await page.goto(`${BASE}/officer/programs?mock=0`, { waitUntil: 'domcontentloaded' })
  const login = page.getByLabel('담당자 비밀번호')
  await login.or(page.locator('.plist__title')).first().waitFor()
  if (await login.count()) { await login.fill('synthetic-e2e-password'); await page.getByRole('button', { name: '로그인', exact: true }).click() }
  await page.locator('.plist__title').waitFor()
  const postings = await (await page.request.get(`${BASE}/api/officer/postings`)).json()
  const builtin = postings.items.find((item) => item.builtin)
  await page.goto(`${BASE}/officer/programs/${builtin.id}?mock=0`, { waitUntil: 'domcontentloaded' })
  await page.locator('.alist__row').first().waitFor()

  // Default 중요도순 on the 확인 필요 tab: 2 items, then 1 item (E2E-001 is 적합).
  const toggle = page.getByRole('group', { name: '정렬' })
  assert.equal(await toggle.getByRole('button', { name: '중요도순' }).getAttribute('aria-pressed'), 'true')
  await waitNumbers(['E2E-002', 'E2E-003'])
  assert.deepEqual(await page.locator('.alist__checks').allInnerTexts(), ['확인 2건', '확인 1건'])
  passed('default 중요도순 orders by 확인 필요 count and shows the count', await numbers())
  await page.locator('.alist__bar').screenshot({ path: `${SHOTS}/sort-bar.png`, animations: 'disabled' })
  await page.screenshot({ path: `${SHOTS}/list-importance.png`, animations: 'disabled' })
  await toggle.getByRole('button', { name: '최신순' }).click()
  await waitNumbers(['E2E-003', 'E2E-002'])
  assert.ok(page.url().includes('sort=latest'))
  await toggle.getByRole('button', { name: '등록순' }).click()
  await waitNumbers(['E2E-002', 'E2E-003'])
  passed('최신순 and 등록순 reorder and persist in the URL')
  await page.reload({ waitUntil: 'domcontentloaded' })
  await page.locator('.alist__row').first().waitFor()
  assert.equal(await page.getByRole('group', { name: '정렬' }).getByRole('button', { name: '등록순' }).getAttribute('aria-pressed'), 'true')
  passed('sort survives a reload')

  // Reject: review screen → 반려 → reject page.
  await page.getByRole('button', { name: /E2E-002 .* 심사 화면 열기/ }).click()
  await page.getByRole('button', { name: '반려', exact: true }).click()
  await page.getByRole('heading', { name: '반려 처리' }).waitFor()
  assert.ok(/\/review\/\d+\/reject/.test(new URL(page.url()).pathname), page.url())
  const reasons = page.locator('.reject-page__reasons label')
  assert.equal(await reasons.count(), 2)
  await reasons.first().click()
  const notice = page.locator('.reject-page__notice')
  assert.equal(await notice.inputValue(), '제출하신 신청이 아래 사유로 반려되었습니다.\n- 주민등록초본: 주민등록초본 발급일이 기준일보다 빠릅니다.')
  await notice.fill(`${await notice.inputValue()}\n보완 후 다시 신청해 주세요.`)
  await page.getByRole('textbox', { name: /내부 메모/ }).fill('E2E 내부 메모')
  passed('반려 opens its own page; picked reasons fill the applicant notice', await reasons.count())
  await page.screenshot({ path: `${SHOTS}/reject-page.png`, fullPage: true, animations: 'disabled' })
  await page.reload({ waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: '반려 처리' }).waitFor()
  passed('reject page URL reloads into the reject page')
  await page.locator('.reject-page__reasons label').first().click()
  await page.getByRole('button', { name: '반려 확정' }).click()
  await page.locator('.reject-page__preview').waitFor()
  await page.screenshot({ path: `${SHOTS}/reject-confirm.png`, animations: 'disabled' })
  await page.getByRole('button', { name: '반려', exact: true }).click()
  await page.getByText('반려했습니다.', { exact: false }).waitFor()
  await waitNumbers(['E2E-003'])
  const stored = await (await page.request.get(`${BASE}/api/__e2e/review/E2E-002`)).json()
  assert.equal(stored.decision, 'reject')
  assert.equal(stored.status, 'decided')
  assert.equal(stored.notice, '제출하신 신청이 아래 사유로 반려되었습니다.\n- 주민등록초본: 주민등록초본 발급일이 기준일보다 빠릅니다.')
  assert.equal(stored.memo, '제출하신 신청이 아래 사유로 반려되었습니다.\n- 주민등록초본: 주민등록초본 발급일이 기준일보다 빠릅니다.')
  passed('confirming stores the notice and returns to the list', stored.decision)

  // Cancel path: the reject page returns to the review screen without deciding.
  await page.getByRole('button', { name: /E2E-003 .* 심사 화면 열기/ }).click()
  await page.getByRole('button', { name: '반려', exact: true }).click()
  await page.getByRole('heading', { name: '반려 처리' }).waitFor()
  await page.getByRole('button', { name: '취소', exact: true }).click()
  await page.getByRole('button', { name: '반려', exact: true }).waitFor()
  assert.equal((await (await page.request.get(`${BASE}/api/__e2e/review/E2E-003`)).json()).decision, null)
  passed('취소 returns to the review screen without a decision')

  assert.deepEqual(result.page_errors, [])
  passed('no page errors')
  result.result = 'passed'
} catch (error) {
  result.result = 'failed'
  result.error = String(error).slice(0, 600)
  await page.screenshot({ path: `${SHOTS}/failure.png` }).catch(() => {})
  process.exitCode = 1
} finally {
  await writeFile(`${SHOTS}/e2e-result.json`, JSON.stringify(result, null, 2) + '\n')
  await browser.close()
}
