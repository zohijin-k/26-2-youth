import {readdir,readFile,writeFile} from 'node:fs/promises'
import path from 'node:path'
import assert from 'node:assert/strict'
const root=path.resolve('demo/frontend/dist/assets'),names=await readdir(root)
async function graph(entry,seen=new Set()) {if(seen.has(entry))return seen;seen.add(entry);const source=await readFile(path.join(root,entry),'utf8');for(const match of source.matchAll(/(?:^|;)import(?:[\w{},*\s]*from)?["']([^"']+\.js)["']/g)){if(match[1].startsWith('.'))await graph(path.basename(match[1]),seen)}return seen}
const mock=names.find(x=>/^mock-data-.*\.js$/.test(x));assert.ok(mock,'Mock data must remain a separate generated chunk')
const result={mock_chunk_separate:true,static_graphs:{}}
for(const prefix of ['ApplicantApp-','OfficerApp-']){const entry=names.find(x=>x.startsWith(prefix)&&x.endsWith('.js'));assert.ok(entry);const chunks=[...await graph(entry)];assert.equal(chunks.includes(mock),false);result.static_graphs[prefix]={chunks:chunks.length,contains_mock_data:false}}
const api=await readFile('demo/frontend/src/api.ts','utf8');assert.match(api,/await import\('\.\/pages\/officer\/mock-data\.ts'\)/)
await writeFile(new URL('./bundle-verification.json',import.meta.url),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result))
