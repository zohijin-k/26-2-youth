import { chromium } from '/tmp/renewal-npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright/index.mjs'
import assert from 'node:assert/strict'
import { readFile, writeFile } from 'node:fs/promises'
const fixtures = JSON.parse(await readFile('/tmp/renewal-master2-visual-fixtures/manifest.json', 'utf8'))
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1100 }, locale: 'ko-KR', timezoneId: 'Asia/Seoul', reducedMotion: 'reduce' })
const page = await context.newPage()
const errors = []
page.on('pageerror', error => errors.push(error.message))
try {
  await page.goto('http://127.0.0.1:5183/officer/programs/new?mock=0', { waitUntil: 'domcontentloaded' })
  await page.getByLabel('담당자 비밀번호').fill('synthetic-visual-password')
  await page.screenshot({ path: new URL('./shots/officer-login.png', import.meta.url).pathname, fullPage: true })
  await page.getByRole('button', { name: '로그인', exact: true }).click()
  await page.locator('#program-notice').waitFor()
  await page.locator('#program-notice').setInputFiles(fixtures.notice)
  await page.locator('#program-forms').setInputFiles(fixtures.form)
  await page.locator('#program-supplemental').fill('합성 자료로만 확인하는 공개 안내입니다.')
  await page.screenshot({ path: new URL('./shots/officer-one-shot-upload.png', import.meta.url).pathname, fullPage: true })
  const pending = page.waitForResponse(response => new URL(response.url()).pathname === '/api/officer/programs/analyze')
  await page.getByRole('button', { name: '분석하기', exact: true }).click()
  const response = await pending
  assert.equal(response.status(), 201)
  const data = await response.json()
  await page.locator('#preview-title-input').waitFor()
  await page.screenshot({ path: new URL('./shots/officer-analyzed-preview.png', import.meta.url).pathname, fullPage: true })
  assert.equal(await page.getByRole('button', { name: '올리기 (게시)', exact: true }).isDisabled(), true)
  assert.equal(data.analysis.title.needs_review, true)
  assert.ok(data.analysis.required_docs.length)
  await writeFile(new URL('./visual-preview.json', import.meta.url), JSON.stringify({ posting_id: data.posting.id, url: page.url(), pending: data.publish_blockers, errors }, null, 2) + '\n')
  console.log(JSON.stringify({ success: true, posting_id: data.posting.id, errors }))
} catch (error) { console.log(JSON.stringify({url:page.url(),errors,message:error.message})); await page.screenshot({path:new URL('./shots/preview-failure.png',import.meta.url).pathname,fullPage:true}); throw error } finally { await browser.close() }
