const { chromium } = await import(process.env.PLAYWRIGHT_PACKAGE ?? '/tmp/renewal-npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright/index.mjs')
import { writeFile } from 'node:fs/promises'
const phase = process.env.VISUAL_PHASE ?? 'baseline'
const shots = new URL('./shots/', import.meta.url).pathname.replace(/\/$/, '')
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, locale: 'ko-KR', timezoneId: 'Asia/Seoul', reducedMotion: 'reduce' })
const page = await context.newPage()
const errors=[]
page.on('pageerror', error=>errors.push(String(error)))
const captures=[]
async function capture(name) {
  await page.evaluate(async()=>{await document.fonts.ready})
  await page.screenshot({ path: `${shots}/${phase}-${name}.png`, fullPage: true, animations: 'disabled' })
  captures.push({name,url:page.url(),path:`${shots}/${phase}-${name}.png`,viewport:{width:1440,height:1000}})
}
try {
  await page.goto('http://127.0.0.1:5183/officer?mock=1', {waitUntil:'networkidle'})
  await page.getByRole('heading',{name:'사업 목록',exact:true}).waitFor()
  await page.locator('.plist__card').first().waitFor()
  await capture('programs')
  await page.goto('http://127.0.0.1:5183/officer/province?mock=1', {waitUntil:'networkidle'})
  await page.locator('.alist__open').first().waitFor()
  await capture('list')
  await page.locator('.alist__open').first().click()
  await page.locator('.review__head .review__name').waitFor()
  await page.locator('.review__left img').first().waitFor()
  await page.waitForLoadState('networkidle')
  await capture('review')
  await writeFile(new URL(`./visual-${phase}.json`, import.meta.url),JSON.stringify({captures,errors},null,2)+'\n')
  console.log(JSON.stringify({captures,errors},null,2))
} finally {await browser.close()}
