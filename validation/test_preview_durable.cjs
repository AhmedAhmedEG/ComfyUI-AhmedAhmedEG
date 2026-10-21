const fs=require('fs'),assert=require('assert');
const {JSDOM}=require('../.validation/ui/node_modules/jsdom');
const browsers=[];
const code=fs.readFileSync('web/js/minimax_preview.js','utf8').replace('export function','function');
const tick=()=>new Promise(r=>setTimeout(r,0));

function browser(storage={},properties={}) {
  const dom=new JSDOM('<body><div id="root"></div>',{url:'http://localhost/',runScripts:'outside-only'}),w=dom.window;
  browsers.push(dom);
  for(const [k,v] of Object.entries(storage))w.localStorage.setItem(k,v);
  w.HTMLMediaElement.prototype.pause=()=>{};
  w.HTMLMediaElement.prototype.load=function(){this.currentTime=0;};
  w.URL.createObjectURL=b=>'blob:http://localhost/'+b.key;w.URL.revokeObjectURL=()=>{};
  w.eval(code);
  let options=properties,revision=1;const calls=[];
  const api={apiURL:p=>p,fetchApi:async(path,request)=>{
    if(path.includes('/project/takes'))return {ok:true,json:async()=>['a','b'].map(take_id=>({take_id,clip_id:'one',has_frames:true,updated_at:1}))};
    if(path.includes('/preview/media'))return {ok:true,clone(){return this;},blob:async()=>({size:10,key:new URL(path,'http://localhost').searchParams.get('key')})};
    const body=JSON.parse(request.body);calls.push(body);
    return {ok:true,json:async()=>({found:true,project_id:'durable',scope:body.scope,label:'Completed',key:revision+'-'+body.scope+'-'+body.stream+'-'+body.take_id})};
  }};
  const root=w.document.querySelector('#root');
  const player=w.installSmartPreview({root,toolbar:w.document.createElement('div'),timelinePanel:w.document.createElement('div'),inspector:w.document.createElement('div'),node:{id:17},api,
    standalone:true,getTimeline:()=>({project_id:'durable',clips:[{id:'one'}]}),getOptions:()=>options,saveOptions:o=>options=o});
  return {dom,w,root,player,calls,rev:v=>revision=v,storage:()=>Object.fromEntries(Array.from({length:w.localStorage.length},(_,i)=>{const k=w.localStorage.key(i);return [k,w.localStorage.getItem(k)];}))};
}

(async()=>{
  const first=browser();await tick();await tick();
  const scope=first.root.querySelector('[aria-label="Preview scope"]');scope.value='full';scope.onchange();await tick();await tick();
  const stage=first.root.querySelector('[aria-label="Preview Stage"]');stage.value='pre_refine';stage.onchange();await tick();await tick();
  const video=first.root.querySelector('video');Object.defineProperty(video,'duration',{value:20,configurable:true});video.onloadedmetadata();
  video.currentTime=4.25;video.ontimeupdate();first.w.dispatchEvent(new first.w.Event('pagehide'));
  const stored=first.storage();first.player.dispose();first.dom.window.close();

  // A fresh browser context has no module/session cache or saved node properties.
  const second=browser(stored,{});await tick();await tick();
  assert.equal(second.root.querySelector('[aria-label="Preview scope"]').value,'full');
  assert.equal(second.root.querySelector('[aria-label="Preview Stage"]').value,'pre_refine');
  const restored=second.root.querySelector('video');Object.defineProperty(restored,'duration',{value:20,configurable:true});restored.onloadedmetadata();
  assert.equal(restored.currentTime,4.25,'Playback position survives browser restart for the same media revision');
  second.rev(2);await second.player.refresh();await tick();restored.onloadedmetadata();
  assert.equal(restored.currentTime,0,'A replacement take never inherits an older revision playback position');
  assert(restored.src.includes('2-full-pre_refine-undefined'),'New generations replace old buffered media');
  second.player.dispose();second.dom.window.close();
  console.log('Preview durability passed: fresh-browser preferences, scope/stage, playback resume and regenerated media revisions.');
})().catch(e=>{console.error(e);for(const dom of browsers)dom.window.close();process.exitCode=1;});
