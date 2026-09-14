/* Query the complete frozen snapshot in a worker. Keep only four decoded shards.
   Counts/ranges in the manifest let ordinary pagination skip unrelated files. */
'use strict';
const cache = new Map();
const root = new URL('graph-data/', self.location.href);
const version = new URL(self.location.href).searchParams.get('v');
function snapshotUrl(file){const u=new URL(file,root);if(version)u.searchParams.set('v',version);return u;}
let manifestPromise, overviewPromise;
const getManifest = () => manifestPromise ||= fetch(snapshotUrl('manifest.json'),{cache:'no-cache'}).then(checkedJson);
const getOverview = () => overviewPromise ||= fetch(snapshotUrl('overview.json'),{cache:'no-cache'}).then(checkedJson);
async function checkedJson(r) { if (!r.ok) throw Error('공유 데이터 조회 실패: '+r.status); return r.json(); }
async function load(part) {
  if (cache.has(part.file)) { const v=cache.get(part.file);cache.delete(part.file);cache.set(part.file,v);return v; }
  const url=new URL(part.file,root);url.searchParams.set('sha256',part.sha256);
  const r=await fetch(url);
  if(!r.ok)throw Error('데이터 조각 조회 실패: '+r.status);
  if(typeof DecompressionStream==='undefined')throw Error('압축 데이터를 읽으려면 최신 Chrome, Edge, Firefox 또는 Safari를 사용하세요.');
  const buffer=await r.arrayBuffer();
  const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',buffer)),x=>x.toString(16).padStart(2,'0')).join('');
  if(digest!==part.sha256)throw Error('데이터 무결성 확인 실패. 페이지를 새로고침하세요.');
  const stream=new Blob([buffer]).stream().pipeThrough(new DecompressionStream('gzip'));
  const rows=JSON.parse(await new Response(stream).text());
  cache.set(part.file,rows);while(cache.size>4)cache.delete(cache.keys().next().value);
  return rows;
}
const object=(cols,row)=>Object.fromEntries(cols.map((k,i)=>[k,row[i]]));
const fold=s=>String(s||'').replace(/[A-Z]/g,c=>c.toLowerCase()); // SQLite LIKE default ASCII case folding
const contains=(s,q)=>fold(s).includes(fold(q));
async function record(id,m) {
  const part=m.records.find(p=>p.first<=id&&p.last>=id);
  if(!part)throw Error('자료 식별자를 찾을 수 없습니다.');
  const row=(await load(part)).find(r=>r[0]===id);
  if(!row)throw Error('자료 식별자를 찾을 수 없습니다.');
  return object(m.record_columns,row);
}
async function hydrate(row,m) {
  const it=object(m.item_columns,row);it.record=await record(it.record_id,m);
  it.semantic_status=it.concept_ids.length?'candidate_pending_human_review':'no_match_to_current_concept_draft';
  return it;
}
function itemCount(part,f) {
  return part.stats.reduce((n,[p,k,total,mapped,concepts,first,last])=>
    n+((f.portal&&p!==f.portal)||(f.basis&&k!==f.basis)||(f.record&&(f.record<first||f.record>last))?0:
      f.concept?(concepts[f.concept]||0):f.mode==='all'?total:mapped),0);
}
function matchItem(r,f) {
  return (!f.portal||r[2]===f.portal)&&(!f.basis||r[3]===f.basis)&&(!f.record||r[1]===f.record)&&
    (!f.q||contains(r[4],f.q)||contains(r[5],f.q))&&
    (f.concept?r[15].includes(f.concept):f.mode==='all'||r[15].length>0);
}
async function query(endpoint,params,progress) {
  const m=await getManifest(),overview=await getOverview();
  if(endpoint==='overview')return overview;
  if(endpoint==='item') {
    const id=Number(params.id),part=m.items.find(p=>p.first<=id&&p.last>=id);
    const row=part&&(await load(part)).find(r=>r[0]===id);
    if(!row)throw Error('원문 항목을 찾을 수 없습니다.');
    const it=await hydrate(row,m);
    const digest=new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(it.evidence_id||'')));
    const receiptPart=m.receipts[digest[0].toString(16).padStart(2,'0')];
    it.receipt=receiptPart?(await load(receiptPart))[it.evidence_id]||{}:{};
    it.human_approved=false;return it;
  }
  if(!['paths','registrations'].includes(endpoint))throw Error('지원하지 않는 공유 데이터 경로입니다.');
  const f=Object.fromEntries(['portal','concept','basis','q','record'].map(k=>[k,String(params[k]||'').trim().slice(0,200)]));
  f.mode=params.mode||'mapped';
  const page=Number(params.page||1);
  if(!Number.isInteger(page)||page<1||page>1000000)throw Error('페이지 범위 오류');
  if(f.portal&&!overview.portals.some(p=>p.portal_id===f.portal))throw Error('알 수 없는 포털');
  if(f.concept&&!overview.concepts.some(c=>c.id===f.concept))throw Error('알 수 없는 개념');
  if(!['mapped','all'].includes(f.mode)||!['','catalog_label','documented_field','declared_output'].includes(f.basis))throw Error('검색 조건 오류');
  const registrations=endpoint==='registrations';
  if(f.record&&!registrations)await record(f.record,m);
  const dynamic=!!f.q||(!registrations&&!!f.record);
  const partCount=registrations?p=>f.portal?(p.portals[f.portal]||0):p.rows:p=>itemCount(p,f);
  const parts=m[registrations?'records':'items'].filter(p=>partCount(p)>0);
  const rows=[];let total=0,skip=(page-1)*24,visited=0;
  if(!dynamic)total=parts.reduce((n,p)=>n+partCount(p),0);
  for(const part of parts) {
    if(!dynamic&&skip>=partCount(part)){skip-=partCount(part);continue;}
    for(const row of await load(part)) {
      const match=registrations?(!f.portal||row[1]===f.portal)&&(!f.q||contains(row[2],f.q)):matchItem(row,f);
      if(!match)continue;
      if(dynamic)total++;
      if(skip>0){skip--;continue;}
      if(rows.length<24)rows.push(row);
    }
    visited++;
    if(dynamic)progress(`공유 데이터 검색 중 · ${visited}/${parts.length}개 파일 확인 (전체 포털 검색은 시간이 걸릴 수 있습니다.)`);
    if(!dynamic&&rows.length>=24)break;
  }
  const results=[];
  for(const row of rows)results.push(registrations?object(m.record_columns,row):await hydrate(row,m));
  return {snapshot_at:m.snapshot_at,total,page,page_size:24,pages:Math.ceil(total/24),results,
    view:registrations?'registrations':'items',filters:f,all_matches_indexed:true,human_approved:false,
    records_with_no_items_included:true};
}
self.onmessage=async e=>{
  const {id,endpoint,params}=e.data;
  try { const data=await query(endpoint,params||{},message=>self.postMessage({id,progress:message}));self.postMessage({id,data}); }
  catch(error) { self.postMessage({id,error:error.message}); }
};
