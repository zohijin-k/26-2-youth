import {chromium} from '/tmp/renewal-npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright/index.mjs'
import {readFile,writeFile} from 'node:fs/promises'
import assert from 'node:assert/strict'
const browser=await chromium.launch({headless:true}),context=await browser.newContext(),page=await context.newPage(),result={api_requests:[],errors:[]}
page.on('request',r=>{const u=new URL(r.url());if(u.pathname.startsWith('/api/'))result.api_requests.push(u.pathname)});page.on('pageerror',e=>result.errors.push(e.message))
try{await page.goto('http://127.0.0.1:5185/officer?mock=1',{waitUntil:'networkidle'});await page.locator('.plist__card').first().waitFor();await page.goto(JSON.parse(await readFile(new URL('./visual-baseline.json',import.meta.url))).url,{waitUntil:'networkidle'});await page.locator('.review__name').waitFor();assert.equal(result.api_requests.length,0);assert.equal(result.errors.length,0);result.result='passed';console.log('Mock list/detail work without API or login')}finally{await writeFile(new URL('./mock-verification.json',import.meta.url),JSON.stringify(result,null,2)+'\n');await browser.close()}
