const fs=require('fs'),assert=require('assert');
const {JSDOM}=require('../.validation/ui/node_modules/jsdom');
const dom=new JSDOM('',{url:'http://localhost/',runScripts:'outside-only'}),w=dom.window;
const stored=new Map();let downloads=0,fail=false;
const response=key=>({ok:true,headers:{get:()=> '100'},blob:async()=>({size:100,key}),clone(){return response(key);}});
w.caches={open:async()=>({match:async k=>stored.get(String(k)),put:async(k,r)=>stored.set(String(k),r),keys:async()=>[...stored.keys()],delete:async k=>stored.delete(String(k))})};
w.eval(fs.readFileSync('web/js/minimax_preview.js','utf8').replace('export function','function')+'\nglobalThis.fetchPreview=bufferedPreview;globalThis.clearSession=()=>previewMedia.clear();');
const api={apiURL:p=>'http://localhost'+p,fetchApi:async p=>{downloads++;if(fail)throw Error('offline');return response(p);}};
(async()=>{
  await Promise.all([w.fetchPreview(api,'/one'),w.fetchPreview(api,'/one')]);
  assert.equal(downloads,1,'Concurrent players share one download');
  w.clearSession();await w.fetchPreview(api,'/one');assert.equal(downloads,1,'Browser storage survives session-memory eviction');
  fail=true;await assert.rejects(w.fetchPreview(api,'/two'));fail=false;
  await w.fetchPreview(api,'/two');assert.equal(downloads,3,'A failed transfer can be retried');
  for(let i=0;i<35;i++)await w.fetchPreview(api,'/take'+i);
  assert.equal(stored.size,32,'Persistent cache has a bounded take count');
  dom.window.close();console.log('Preview cache passed: shared downloads, persistent reuse, failure recovery, bounded storage.');
})().catch(e=>{console.error(e);dom.window.close();process.exitCode=1;});
