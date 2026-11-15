import { chromium } from '/tmp/renewal-npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright/index.mjs'
import { readFile,writeFile,mkdir } from 'node:fs/promises'
const phase=process.argv[2] || 'before'; const base='http://127.0.0.1:5187'
const fixture=JSON.parse(await readFile(new URL('../visual-before-result.json',import.meta.url)))
const dir=new URL(`./shots/${phase}/`,import.meta.url); await mkdir(dir,{recursive:true})
const browser=await chromium.launch({headless:true}); const ctx=await browser.newContext({viewport:{width:1440,height:900},locale:'ko-KR',timezoneId:'Asia/Seoul',reducedMotion:'reduce'})
await ctx.request.post(`${base}/api/officer/login`,{data:{password:'synthetic-visual-password'}})
// Keep the list fixture identical to the baseline despite later synthetic QA programs.
await ctx.route('**/api/officer/postings',async route=>{const response=await route.fetch();const body=await response.json();body.items=body.items.filter(item=>item.builtin||item.id===fixture.posting_id);await route.fulfill({response,json:body})})
const page=await ctx.newPage(); const result={phase,surfaces:[],errors:[]}; page.on('pageerror',e=>result.errors.push(e.message))
const baseline = JSON.parse(await readFile(new URL('../visual-baseline.json',import.meta.url)));
const targets=[['login','/officer/login'],['upload','/officer/programs/new?mock=0'],['program-list','/officer?mock=0'],['preview',`/officer/programs/${fixture.posting_id}?mock=0&tab=settings`],['workspace',`/officer/programs/${fixture.posting_id}?mock=0`],['generic-review',`/officer/programs/${fixture.posting_id}/applications/${fixture.application_id}?mock=0`],['job-list','/officer/province?mock=1'],['job-review',(() => { const url = new URL(baseline.url); return url.pathname + url.search })()],['job-auth-list','/officer/programs/1/province?mock=0'],['job-auth-review',`/officer/programs/1/province/review/${fixture.job_application_id}?mock=0`]]
try{for(const [name,path] of targets){
await page.goto(base+path,{waitUntil:'networkidle'}); await page.evaluate(()=>document.fonts.ready); await page.waitForTimeout(200)
if(name==='job-review') await page.locator('.review__name').waitFor()
await page.screenshot({path:new URL(name+'.png',dir).pathname,animations:'disabled'})
const metric=await page.evaluate(()=>{const visible=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(e).visibility!=='hidden'};const all=[...document.querySelectorAll('main *, .program-officer-workspace *')].filter(e=>e.childNodes.length&&[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())&&visible(e)&&!e.closest('.viewer,.template-editor__page')); const buttons=[...document.querySelectorAll('button')].filter(e=>visible(e)&&e.getBoundingClientRect().top<900&&e.getBoundingClientRect().bottom>0);return{buttons:buttons.length,min_font:Math.min(...all.map(e=>parseFloat(getComputedStyle(e).fontSize))),native_file_buttons:[...document.querySelectorAll('input[type=file]')].filter(e=>visible(e)&&e.getBoundingClientRect().top<900&&e.getBoundingClientRect().bottom>0).length,visible_disclosures:[...document.querySelectorAll('summary')].filter(e=>visible(e)&&e.getBoundingClientRect().top<900&&e.getBoundingClientRect().bottom>0).length,primary_buttons:buttons.filter(e=>e.classList.contains('btn--primary')).length,button_labels:buttons.map(e=>e.getAttribute('aria-label')||e.textContent.trim()),overflow:document.documentElement.scrollWidth>innerWidth}})
const widths=[]; for(const width of [1280,1024]){await page.setViewportSize({width,height:900});await page.waitForTimeout(100);widths.push({width,overflow:await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)})} await page.setViewportSize({width:1440,height:900})
result.surfaces.push({name,path,...metric,widths}); console.log(name+' captured')
}} finally{await writeFile(new URL(`./surfaces-${phase}.json`,import.meta.url),JSON.stringify(result,null,2)+'\n');await browser.close()}
