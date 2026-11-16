/** Loopback capture: officer uploads the synthetic notice with a fake provider; the preview editor's
 * "추가 안내" shows provider suggestions with the AI chip. One screenshot, assertions in shots/e2e-result.json. */
const { chromium } = await import(process.env.PLAYWRIGHT_PACKAGE ?? '/tmp/renewal-npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright/index.mjs')
import assert from 'node:assert/strict'
import { writeFile, mkdir } from 'node:fs/promises'

const BASE = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:5192'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(BASE).hostname))
const FILES = '/tmp/jbai-schema-check-e2e/files'
const SHOTS = new URL('./shots/', import.meta.url).pathname.replace(/\/$/, '')
await mkdir(SHOTS, { recursive: true })
const result = { assertions: [], page_errors: [], request_failures: [], shot: null }
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ deviceScaleFactor: 1, locale: 'ko-KR', timezoneId: 'Asia/Seoul', reducedMotion: 'reduce', viewport: { width: 1440, height: 1100 } })
const page = await context.newPage()
page.on('pageerror', error => result.page_errors.push(String(error).slice(0, 200)))
page.on('requestfailed', request => result.request_failures.push(new URL(request.url()).pathname))
page.on('request', request => {
  const url = new URL(request.url())
  if (['http:', 'https:'].includes(url.protocol)) assert.ok(['127.0.0.1', 'localhost'].includes(url.hostname), 'External request is forbidden')
})
const passed = (name, detail = 'O') => { result.assertions.push({ name, detail }); console.log('O ' + name + ' ' + JSON.stringify(detail)) }

try {
  await page.goto(`${BASE}/officer/programs/new?mock=0`, { waitUntil: 'domcontentloaded' })
  await page.getByLabel('담당자 비밀번호').fill('synthetic-e2e-password')
  await page.getByRole('button', { name: '로그인', exact: true }).click()
  await page.locator('#program-notice').waitFor({ state: 'attached' })
  await page.locator('#program-notice').setInputFiles(`${FILES}/notice.pdf`)
  await page.locator('#program-forms').setInputFiles([`${FILES}/form5-consent.pdf`])
  const analyzed = page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/officer/programs/analyze')
  await page.getByRole('button', { name: '분석하기', exact: true }).click()
  const response = await analyzed
  assert.equal(response.status(), 201)
  const data = await response.json()
  const suggestions = data.analysis.suggestions ?? []
  // The fake proposes guidance, a matching age value and a conflicting residence value.
  assert.deepEqual(suggestions.map(row => row.target_id === 'guidance' ? 'guidance' : row.type).sort(), ['age', 'guidance'])
  assert.ok(suggestions.every(row => row.needs_review === true && row.confidence === 0))
  passed('only verified suggestions reach the screen', suggestions.length)
  await page.locator('#preview-title-input').waitFor()
  const notice = page.locator('details.program-preview__notice')
  await notice.locator('summary').click()
  const cards = notice.locator('section[aria-label="제안 확인"]')
  assert.equal(await cards.count(), 2)
  for (let index = 0; index < 2; index += 1) {
    assert.equal(await cards.nth(index).locator('.om-chip').innerText(), 'AI 제안 · 담당자 확인 필요')
  }
  assert.equal(await notice.locator('p').count(), data.analysis.warnings.length)
  passed('every suggestion card carries the AI chip; warning lines do not', { cards: 2, warnings: data.analysis.warnings.length })
  await notice.scrollIntoViewIfNeeded()
  await page.evaluate(async () => { await document.fonts.ready })
  result.shot = `${SHOTS}/preview-ai-suggestions.png`
  await page.screenshot({ path: result.shot, fullPage: false, animations: 'disabled' })
  await notice.screenshot({ path: `${SHOTS}/preview-ai-suggestions-notice.png`, animations: 'disabled' })
  assert.deepEqual(result.page_errors, [])
  passed('no page errors')
  result.result = 'passed'
} catch (error) {
  result.result = 'failed'
  result.error = String(error).slice(0, 300)
  process.exitCode = 1
} finally {
  await writeFile(`${SHOTS}/e2e-result.json`, JSON.stringify(result, null, 2) + '\n')
  await browser.close()
}
