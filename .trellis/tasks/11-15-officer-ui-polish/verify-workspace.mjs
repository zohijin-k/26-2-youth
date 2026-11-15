import {chromium} from '/tmp/renewal-npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright/index.mjs'
import {readFile,writeFile} from 'node:fs/promises'
import assert from 'node:assert/strict'
const base='http://127.0.0.1:5185', fixture=JSON.parse(await readFile(new URL('./visual-before-result.json',import.meta.url)))
const browser=await chromium.launch({headless:true}),ctx=await browser.newContext({viewport:{width:1440,height:900}}),page=await ctx.newPage(),result={checks:[],geometry:[],errors:[]}
page.on('pageerror',e=>result.errors.push(e.message));const pass=x=>{result.checks.push(x);console.log('PASS '+x)}
try{
await ctx.request.post(`${base}/api/officer/login`,{data:{password:'synthetic-visual-password'}})
await page.goto(`${base}/officer/programs/${fixture.posting_id}?mock=0`,{waitUntil:'networkidle'});const nav=page.getByRole('tablist',{name:'사업 작업 공간',exact:true});await nav.getByRole('tab',{name:'신청 목록',exact:true}).focus();await page.keyboard.press('ArrowRight');await page.waitForFunction(()=>document.querySelector('.program-preview h1')===document.activeElement);pass('settings chip arrow navigation moves focus to loaded preview heading')
await page.goto(`${base}/officer/programs/${fixture.posting_id}?mock=0`,{waitUntil:'networkidle'});await page.getByRole('tab',{name:/처리 완료/}).click();await page.locator('.alist__open').first().waitFor();await page.waitForFunction(()=>!document.querySelector('.alist__open')?.disabled)
await page.getByRole('searchbox',{name:'신청번호 또는 성명 검색'}).fill('NO-SYNTHETIC-MATCH');await page.getByRole('checkbox',{name:'전체 선택',exact:true}).check();await page.getByText('조건에 맞는 신청이 없습니다.',{exact:false}).waitFor();assert.equal(await page.locator('.om-generic-list__selection').count(),0);pass('debounced search removes invisible bulk selections')
await page.getByRole('button',{name:'조건 지우기',exact:true}).click();await page.locator('.alist__open').first().waitFor();await page.waitForFunction(()=>!document.querySelector('.alist__open')?.disabled)
const more=page.getByRole('button',{name:/JP-.* 더보기$/}).first();await more.focus();await page.keyboard.press('Enter');await page.keyboard.press('Escape');assert.equal(await more.evaluate(e=>e===document.activeElement),true);pass('generic row menu Escape restores opener focus')
await page.goto(`${base}/officer/programs/${fixture.posting_id}/applications/${fixture.application_id}?mock=0`,{waitUntil:'networkidle'});await page.locator('.om-review__process').waitFor()
for(const width of [1440,1280,1024]){await page.setViewportSize({width,height:900});await page.waitForTimeout(100);const box=await page.locator('.om-review__process').boundingBox();assert.ok(box.y+box.height<=900);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);result.geometry.push({width,footer_bottom:box.y+box.height,horizontal_overflow:false})}pass('review footer fits 900px at all three required widths')
assert.equal(result.errors.length,0);result.result='passed'
}catch(e){result.result='failed';result.errors.push(String(e));console.error(e.stack);process.exitCode=1}finally{await writeFile(new URL('./workspace-verification.json',import.meta.url),JSON.stringify(result,null,2)+'\n');await browser.close()}
