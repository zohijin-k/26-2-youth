/** 반려 탭 확인: 11-16-officer-sort-reject/e2e_backend.py(신청 3건이 든 임시 DB)에 붙여 돌린다. */
const { chromium } = await import(process.env.PLAYWRIGHT_PACKAGE)
import assert from 'node:assert/strict'
import { writeFile, mkdir } from 'node:fs/promises'

const BASE = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:5196'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(BASE).hostname))
const SHOTS = process.env.SHOTS
await mkdir(SHOTS, { recursive: true })
const result = { assertions: [], page_errors: [] }
const browser = await chromium.launch({ headless: true })
const page = await (await browser.newContext({ locale: 'ko-KR', timezoneId: 'Asia/Seoul', viewport: { width: 1440, height: 1000 } })).newPage()
page.on('pageerror', (error) => result.page_errors.push(String(error).slice(0, 200)))
page.on('request', (request) => {
  const url = new URL(request.url())
  if (['http:', 'https:'].includes(url.protocol)) assert.ok(['127.0.0.1', 'localhost'].includes(url.hostname), '외부 요청 금지')
})
const passed = (name, detail = 'O') => { result.assertions.push({ name, detail }); console.log('O ' + name + ' ' + JSON.stringify(detail)) }

try {
  await page.goto(`${BASE}/officer/programs?mock=0`, { waitUntil: 'domcontentloaded' })
  const login = page.getByLabel('담당자 비밀번호')
  await login.or(page.locator('.plist__title')).first().waitFor()
  if (await login.count()) { await login.fill('synthetic-e2e-password'); await page.getByRole('button', { name: '로그인', exact: true }).click() }
  await page.locator('.plist__title').waitFor()
  const builtin = (await (await page.request.get(`${BASE}/api/officer/postings`)).json()).items.find((item) => item.builtin)
  await page.goto(`${BASE}/officer/programs/${builtin.id}?mock=0`, { waitUntil: 'domcontentloaded' })
  await page.locator('.alist__row').first().waitFor()

  const tabs = page.getByRole('tablist', { name: '신청 구분' }).getByRole('tab')
  assert.deepEqual((await tabs.allInnerTexts()).map((text) => text.replace(/\s*\d+\s*건?$/, '').replace(/\s+/g, ' ').trim()), ['확인 필요', '적합', '처리 완료', '반려'])
  passed('반려 탭이 처리 완료 바로 오른쪽에 있다')

  // 반려 페이지로 한 건 반려한다.
  await page.getByRole('button', { name: /E2E-002 .* 심사 화면 열기/ }).click()
  await page.getByRole('button', { name: '반려', exact: true }).click()
  await page.getByRole('heading', { name: '반려 처리' }).waitFor()
  await page.locator('.reject-page__reasons label').first().click()
  await page.getByRole('button', { name: '반려 확정' }).click()
  await page.getByRole('button', { name: '반려', exact: true }).click()
  await page.getByText('반려했습니다.', { exact: false }).waitFor()

  const rejectedTab = page.getByRole('tab', { name: /^반려/ })
  await page.waitForFunction(() => /반려\s*1/.test([...document.querySelectorAll('[role=tab]')].map((el) => el.textContent).join('|')))
  await rejectedTab.click()
  await page.locator('.rejection-table').waitFor()
  assert.equal(await rejectedTab.getAttribute('aria-selected'), 'true')
  assert.ok(new URL(page.url()).searchParams.get('status') === 'reject' && new URL(page.url()).searchParams.get('queue') === 'done', page.url())
  const rows = page.locator('.rejection-table tbody tr')
  assert.equal(await rows.count(), 1)
  assert.match(await rows.first().innerText(), /E2E-002[\s\S]*가상신청2[\s\S]*제출하신 신청이 아래 사유로 반려되었습니다\.[\s\S]*주민등록초본/)
  passed('반려 탭에 반려한 건과 신청자 안내가 보인다', await rows.count())
  await page.screenshot({ path: `${SHOTS}/rejected-tab.png`, animations: 'disabled' })

  await page.reload({ waitUntil: 'domcontentloaded' })
  await page.locator('.rejection-table').waitFor()
  passed('새로고침해도 반려 탭이 유지된다')

  await page.getByRole('button', { name: '전체 보기' }).click()
  await page.getByRole('dialog').getByText('제출하신 신청이 아래 사유로 반려되었습니다.', { exact: false }).waitFor()
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: /E2E-002 .* 심사 화면 열기/ }).click()
  await page.getByText('현재 처리 상태', { exact: false }).waitFor()
  passed('전체 보기 창과 신청번호 → 심사 화면이 열린다')

  assert.deepEqual(result.page_errors, [])
  passed('페이지 오류 없음')
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
