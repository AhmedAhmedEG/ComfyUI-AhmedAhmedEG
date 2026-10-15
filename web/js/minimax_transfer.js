import {api} from '../../scripts/api.js';

export function transferRequest(path, {body, blob=false, onProgress=()=>{}, signal}={}) {
  const job=crypto.randomUUID();
  const url=path+(path.includes('?')?'&':'?')+'job_id='+encodeURIComponent(job);
  const listener=event=>{if(event.detail?.job_id===job)onProgress(event.detail);};
  api.addEventListener?.('minimax_transfer',listener);
  const progress=(phase,event)=>onProgress({phase,done:event.loaded,total:event.lengthComputable?event.total:0});
  if(typeof XMLHttpRequest==='undefined') {
    return api.fetchApi(url,{method:'POST',body:body instanceof FormData?body:JSON.stringify(body),headers:body instanceof FormData?{}:{'Content-Type':'application/json'},signal})
      .then(async r=>{if(!r.ok)throw Error((await r.json()).error || 'Transfer failed');return blob?r.blob():r.json();})
      .finally(()=>api.removeEventListener?.('minimax_transfer',listener));
  }
  return new Promise((resolve,reject)=>{
    const xhr=new XMLHttpRequest();xhr.open('POST',api.apiURL(url));xhr.withCredentials=true;xhr.responseType='blob';
    if(!(body instanceof FormData))xhr.setRequestHeader('Content-Type','application/json');
    const abort=()=>xhr.abort();
    const cleanup=()=>{api.removeEventListener?.('minimax_transfer',listener);signal?.removeEventListener('abort',abort);};
    xhr.upload.onprogress=e=>progress('Uploading',e);xhr.upload.onload=()=>onProgress({phase:'Processing on server',done:0,total:0});
    xhr.onprogress=e=>progress('Downloading',e);
    xhr.onerror=()=>{cleanup();reject(Error('Transfer connection failed.'));};
    xhr.onabort=()=>{cleanup();reject(new DOMException('Transfer cancelled','AbortError'));};
    xhr.onload=async()=>{cleanup();try{if(xhr.status<200 || xhr.status>=300){const text=await xhr.response.text();let error;try{error=JSON.parse(text).error;}catch{}throw Error(error || `Transfer failed (HTTP ${xhr.status}).`);}resolve(blob?xhr.response:JSON.parse(await xhr.response.text()));}catch(e){reject(e);}};
    signal?.addEventListener('abort',abort,{once:true});if(signal?.aborted){cleanup();reject(new DOMException('Transfer cancelled','AbortError'));return;}
    xhr.send(body instanceof FormData?body:JSON.stringify(body));
  });
}

export function transferLabel(event) {
  return event.total>0?`${event.phase} · ${Math.min(100,Math.round(event.done/event.total*100))}%`:event.phase+'…';
}
