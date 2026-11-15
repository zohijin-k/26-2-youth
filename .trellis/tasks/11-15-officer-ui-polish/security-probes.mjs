import { request } from '/tmp/renewal-npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright/index.mjs'
import { readFile, writeFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
const base='http://127.0.0.1:5185';const fixture=JSON.parse(await readFile(new URL('./visual-before-result.json',import.meta.url)));const files=JSON.parse(await readFile('/tmp/renewal-master2-visual-fixtures/manifest.json'))
const officer=await request.newContext({baseURL:base});const applicant=await request.newContext({baseURL:base});const outsider=await request.newContext({baseURL:base}); const results={}
const json=async(ctx,path,options={})=>{const r=await ctx.fetch(path,options);if(!r.ok())throw Error(`${path}: ${r.status()}`);return r.json()}
try{
await json(officer,'/api/officer/login',{method:'POST',data:{password:'synthetic-visual-password'}})
const created=await json(officer,'/api/officer/programs/analyze',{method:'POST',multipart:{notice_pdf:{name:'notice.pdf',mimeType:'application/pdf',buffer:await readFile(files.notice)},forms_pdfs:{name:'form.pdf',mimeType:'application/pdf',buffer:await readFile(files.form)},supplemental:''}})
const notice=await outsider.get(`/api/postings/${created.posting.id}/files/notice.pdf`)
results.draft_notice_without_cookie={open:notice.ok(),status:notice.status(),observation:notice.ok()?'O':'X'}
const application=await json(applicant,'/api/applications',{method:'POST',data:{program_code:`posting_${fixture.posting_id}`,applicant_flow_version:1}})
const forms=await json(applicant,`/api/applications/${application.id}/forms`);const form=forms[0].form_no
const layout=await json(applicant,`/api/applications/${application.id}/forms/layouts/${form}`)
const fields=Object.entries(layout.fields||{});const field=fields.find(([,f])=>f.field_type==='text'&&!f.autofill_source)?.[0];if(!field)throw Error('Synthetic writable text field required')
const url=`/api/applications/${application.id}/forms/${form}/pages/1.png?preview=false`
const before=await applicant.get(url);if(!before.ok())throw Error('Before page unavailable')
await json(applicant,`/api/applications/${application.id}`,{method:'PATCH',data:{form1:{[field]:'SYNTHETIC ENTERED VALUE 12345'}}})
const saved=await json(applicant,`/api/applications/${application.id}`);if(saved.form1_json[field]!=='SYNTHETIC ENTERED VALUE 12345')throw Error('Probe text was not persisted')
const after=await applicant.get(url);const sha=b=>createHash('sha256').update(b).digest('hex');const a=sha(await before.body()),b=sha(await after.body())
results.preview_false_omits_entered_values={observation:a===b?'O':'X',before_sha256:a,after_sha256:b,persisted_synthetic_text:true,status:after.status()}
console.log(JSON.stringify(results))
}finally{await writeFile(new URL('./security-probes.json',import.meta.url),JSON.stringify(results,null,2)+'\n');await Promise.all([officer.dispose(),applicant.dispose(),outsider.dispose()])}
