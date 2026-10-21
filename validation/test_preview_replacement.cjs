// Exercise real player/cache logic while a replacement transfer is delayed.
const fs = require('fs'), assert = require('assert');
const {JSDOM} = require('../.validation/ui/node_modules/jsdom');
const dom = new JSDOM('<body><div id="root"></div>', {url:'http://localhost/', runScripts:'outside-only'});
const w = dom.window, stored = new Map(), downloads = [];
let generation = 'old', running = false, poll, release, block = false, plays = 0, loads = 0;
const tick = () => new Promise(resolve => setTimeout(resolve, 0));
const settle = async () => {for (let i=0;i<5;i++) await tick();};
w.setInterval = fn => {poll=fn;return 1;};w.clearInterval = () => {};
w.HTMLMediaElement.prototype.pause = () => {};
w.HTMLMediaElement.prototype.load = () => {loads++;};
w.HTMLMediaElement.prototype.play = () => {plays++;return Promise.resolve();};
w.URL.createObjectURL = blob => 'blob:http://localhost/'+blob.key;
w.URL.revokeObjectURL = () => {};
w.caches = {open:async()=>({match:async key=>stored.get(key),put:async(key,r)=>stored.set(key,r),keys:async()=>[...stored.keys()],delete:async key=>stored.delete(key)})};
const response = key => ({ok:true,headers:{get:()=> '100'},blob:async()=>({size:100,key}),clone(){return response(key);}});
const api = {apiURL:path=>'http://localhost'+path,fetchApi:async(path,request)=>{
  if(path.includes('/preview/media')) {
    const key=new URL(path,'http://localhost').searchParams.get('key');downloads.push(key);
    if(block && key==='new-full')await new Promise(resolve=>{release=resolve;});
    return response(key);
  }
  const body=JSON.parse(request.body), key=generation+'-'+body.scope;
  return {ok:true,json:async()=>({found:true,project_id:'replacement',key,scope:body.scope,stream:'final',label:'2/2 clips',run_active:running,clip_generations:{one:generation,two:'unchanged'}})};
}};
w.eval(fs.readFileSync('web/js/minimax_preview.js','utf8').replace('export function','function'));
const root=w.document.querySelector('#root');
let options={scope:'full',autoplay:false};
const player=w.installSmartPreview({root,toolbar:w.document.createElement('div'),timelinePanel:w.document.createElement('div'),inspector:w.document.createElement('div'),node:{id:1},api,standalone:true,
  getTimeline:()=>({project_id:'replacement',clips:[{id:'one'},{id:'two'}]}),getOptions:()=>options,saveOptions:o=>options=o});
(async()=>{
  await settle();const video=root.querySelector('video');
  assert(video.src.endsWith('old-full'));
  assert(downloads.includes('old-latest'),'Full scope also prebuffers Latest without playback');
  const previous=video.src, previousKeys=[...stored.keys()];
  running=true;poll();await settle();
  assert.equal(video.src,previous,'Starting All clips retains the current full video');
  assert.equal(downloads.length,2,'Unchanged generations reuse buffered bytes');
  generation='new';block=true;poll();await settle();
  assert(release,'A new completion automatically starts downloading the new full revision');
  assert(video.src.endsWith('new-full'),'New media is streamable before its full background download finishes');
  assert(!video.hidden);
  video.onloadeddata();video.currentTime=3;
  const streamingSource=video.src,streamingLoads=loads;
  const scope=root.querySelector('[aria-label="Preview scope"]');
  scope.value='latest';scope.onchange();await settle();
  assert(video.src.endsWith('new-latest'),'Switching to Latest does not wait for the Full download');
  scope.value='full';scope.onchange();await settle();
  assert(video.src.endsWith('new-full'),'Switching back to Full streams its pending revision');
  video.currentTime=3;const beforeComplete=loads;
  release();block=false;await settle();
  assert(video.src.endsWith('new-full'));
  assert.equal(loads,beforeComplete,'Completing the background cache never reloads the playing stream');
  assert.equal(video.currentTime,3,'Playback position is uninterrupted when caching finishes');
  assert(downloads.includes('new-latest'),'Latest also prebuffers during an active run');
  assert(previousKeys.every(key=>!stored.has(key)),'Browser storage removes superseded revisions after replacement arrives');
  assert([...stored.keys()].some(key=>key.includes('new-full')),'Replacement full movie is persisted in browser storage');
  assert([...stored.keys()].some(key=>key.includes('new-latest')),'Replacement clip is persisted in browser storage');
  assert.equal(plays,0,'Neither scope prebuffering starts playback');
  player.dispose();dom.window.close();
  console.log('Preview replacement passed: retain during run/transfer, auto-buffer both scopes, refresh persistent revisions, autoplay off.');
})().catch(error=>{console.error(error);player.dispose();dom.window.close();process.exitCode=1;});
