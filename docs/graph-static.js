/* Adapt the existing graph UI to static shards; cancel an obsolete query worker. */
'use strict';
let queryWorker,detailWorker,nextId=0;
const jobs=new Map();
function createWorker() {
  const w=new Worker(new URL('graph-worker.js',document.baseURI));
  w.onmessage=e=>{const {id,data,error,progress}=e.data,j=jobs.get(id);if(!j)return;
    if(progress){const el=document.getElementById('path-count');if(el)el.textContent=progress;return;}
    jobs.delete(id);error?j.reject(Error(error)):j.resolve(new Response(JSON.stringify(data),{headers:{'Content-Type':'application/json'}}));};
  w.onerror=()=>{for(const [id,j] of jobs)if(j.worker===w){j.reject(Error('공유 데이터 검색기를 시작하지 못했습니다. 페이지를 새로고침하세요.'));jobs.delete(id);}};
  return w;
}
function stop(w) {if(!w)return;w.terminate();for(const [id,j] of jobs)if(j.worker===w){j.reject(Error('새 검색으로 전환했습니다.'));jobs.delete(id);}}
async function shareFetch(url) {
  const u=new URL(url,location.href),endpoint=u.pathname.split('/').pop();
  if(endpoint==='overview')return fetch(new URL('graph-data/overview.json',document.baseURI));
  if(endpoint==='item') {stop(detailWorker);detailWorker=createWorker();}
  else {stop(queryWorker);queryWorker=createWorker();}
  const worker=endpoint==='item'?detailWorker:queryWorker,id=++nextId;
  return new Promise((resolve,reject)=>{jobs.set(id,{resolve,reject,worker});worker.postMessage({id,endpoint,params:Object.fromEntries(u.searchParams)});});
}
