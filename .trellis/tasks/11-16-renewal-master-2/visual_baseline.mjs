import { chromium } from '/tmp/renewal-npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright/index.mjs'
import { writeFile } from 'node:fs/promises'
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: 'ko-KR', timezoneId: 'Asia/Seoul', reducedMotion: 'reduce' })
const page = await context.newPage()
const errors = []
page.on('pageerror', (error) => errors.push(error.message))
try {
  const response = await context.request.post('http://127.0.0.1:5183/api/officer/login', { data: { password: 'synthetic-visual-password' } })
  if (!response.ok()) throw new Error('Synthetic login failed')
  await page.goto('http://127.0.0.1:5183/officer/province?mock=1', { waitUntil: 'networkidle' })
  await page.locator('.alist__open').first().click()
  await page.locator('.review__head .review__name').waitFor()
  await page.locator('.review__left img').first().waitFor()
  await page.waitForLoadState('networkidle')
  await page.evaluate(() => document.fonts.ready)
  await page.locator('.review').screenshot({ path: new URL('./shots/baseline-review-component.png', import.meta.url).pathname, animations: 'disabled' })
  await page.screenshot({ path: new URL('./shots/baseline-review-full.png', import.meta.url).pathname, fullPage: true, animations: 'disabled' })
  await writeFile(new URL('./visual-baseline.json', import.meta.url), JSON.stringify({ url: page.url(), errors, review_box: await page.locator('.review').boundingBox() }, null, 2) + '\n')
  console.log(JSON.stringify({ success: true, errors }))
} finally { await browser.close() }
