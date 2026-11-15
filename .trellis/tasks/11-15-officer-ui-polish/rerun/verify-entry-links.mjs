import {chromium} from '/tmp/renewal-npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright/index.mjs'
import {readFile,writeFile} from 'node:fs/promises'
import assert from 'node:assert/strict'
const base='http://127.0.0.1:5187',fixture=JSON.parse(await readFile(new URL('../visual-before-result.json',import.meta.url)))
const browser=await chromium.launch({headless:true}),context=await browser.newContext(),page=await context.newPage(),result={checks:[],errors:[]}
page.on('pageerror',e=>result.errors.push(e.message));const pass=x=>{result.checks.push(x);console.log('PASS '+x)}
try{
await context.request.post(`${base}/api/officer/login`,{data:{password:'synthetic-visual-password'}})
await context.route('**/api/officer/postings',async route=>{const response=await route.fetch(),body=await response.json();body.items=body.items.filter(x=>x.builtin||x.id===fixture.posting_id);await route.fulfill({response,json:body})})
await page.goto(`${base}/officer?mock=0`,{waitUntil:'domcontentloaded'});const row=page.locator('.om-program-card').filter({has:page.locator('.om-menu')});await row.getByRole('button',{name:/더보기$/}).click();await page.getByRole('menuitem',{name:'사업 정보',exact:true}).click();await page.getByRole('heading',{name:'사업 정보',exact:true}).waitFor();assert.equal(new URL(page.url()).searchParams.get('tab'),'info');pass('program row menu opens the selected business info')
await page.getByRole('button',{name:'메뉴 열기',exact:true}).click();await page.getByRole('dialog',{name:'담당자 메뉴'}).getByRole('link',{name:'새 사업 올리기',exact:true}).click();await page.locator('.om-upload-zone').first().waitFor();pass('business drawer opens the new upload screen')
await page.getByRole('button',{name:'메뉴 열기',exact:true}).click();await page.getByRole('dialog',{name:'담당자 메뉴'}).getByRole('link',{name:'사업 목록',exact:true}).click();await page.getByRole('button',{name:'새 사업 올리기',exact:true}).click();await page.locator('.om-upload-zone').first().waitFor();await page.waitForFunction(()=>!document.querySelector('.officer-session-bar'));pass('list primary action opens upload and modern logout ownership survives navigation')
assert.equal(result.errors.length,0);result.result='passed'
}catch(e){result.result='failed';result.errors.push(String(e));console.error(e.stack);process.exitCode=1}finally{await writeFile(new URL('./entry-links.json',import.meta.url),JSON.stringify(result,null,2)+'\n');await browser.close()}
