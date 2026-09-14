// Exercise the actual worker query code against the local SQLite-backed API.
// A simple static HTTP server must serve docs/ on port 8767.
import fs from 'node:fs/promises';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { webcrypto } from 'node:crypto';
const base=process.env.GRAPH_SHARE_URL||'http://127.0.0.1:8767/';
const context=vm.createContext({fetch,URL,Response,Blob,DecompressionStream,TextEncoder,crypto:webcrypto,
  self:{location:{href:new URL('graph-worker.js',base).href}}});
vm.runInContext(await fs.readFile(new URL('../docs/graph-worker.js',import.meta.url),'utf8'),context);
const query=(endpoint,params={})=>{context.endpoint=endpoint;context.params=params;return vm.runInContext('query(endpoint,params,()=>{})',context);};
const cases=[
 ['paths',{}],['paths',{mode:'all',page:'171775'}],
 ['paths',{portal:'kosis',concept:'measure:unemployment-rate'}],
 ['paths',{portal:'kosis',concept:'measure:unemployment-rate',page:'2'}],
 ['paths',{portal:'kosis',concept:'measure:unemployment-rate',basis:'documented_field',q:'실업'}],
 ['paths',{portal:'hrfco',mode:'all',q:'%_'}],
 ['registrations',{}],['registrations',{portal:'busan'}],
 ['registrations',{portal:'busan',page:'523'}],['registrations',{portal:'hrfco',q:'수위'}],
];
let checked=0;
for(const [endpoint,params] of cases){
 const actual=await query(endpoint,params),r=await fetch('http://127.0.0.1:8766/api/concepts/graph/'+endpoint+'?'+new URLSearchParams(params));
 assert.equal(r.status,200);const expected=await r.json();
 assert.equal(actual.total,expected.total);assert.equal(actual.pages,expected.pages);
 assert.equal(JSON.stringify(actual.results.map(r=>r.id)),JSON.stringify(expected.results.map(r=>r.id)));
 if(endpoint==='paths')assert.equal(JSON.stringify(actual.results.map(r=>r.concept_ids)),JSON.stringify(expected.results.map(r=>r.concept_ids)));
 console.log('PASS',endpoint,JSON.stringify(params),actual.total);checked++;
}
const unemployment=await query('paths',{portal:'kosis',concept:'measure:unemployment-rate'});
const item=await query('item',{id:String(unemployment.results[0].id)});
assert.ok(item.receipt.sha256);assert.equal(item.human_approved,false);
const scoped=await query('paths',{record:item.record_id,mode:'all'});
assert.ok(scoped.total>0&&scoped.results.every(i=>i.record_id===item.record_id));checked+=2;
for(const params of [{portal:'nonexistent'},{basis:'bad'},{page:'0'},{concept:'fake'},{record:'missing'}]){
 await assert.rejects(()=>query('paths',params));checked++;
}
const report={passed:true,cases:checked,query_totals_and_result_ids_match_local_api:true,receipt_verified:true};
await fs.writeFile(new URL('../docs/graph-data/query-validation.json',import.meta.url),JSON.stringify(report,null,2));
console.log(JSON.stringify(report));
