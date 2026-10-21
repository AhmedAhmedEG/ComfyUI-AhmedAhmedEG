const fs=require('fs'),assert=require('assert');
const {JSDOM}=require('../.validation/ui/node_modules/jsdom');
const dom=new JSDOM('<div id="root"></div>',{url:'http://localhost/',runScripts:'outside-only'}),w=dom.window;
let revision='one',scope='latest',release,held=false,fail=false;const requests=[],saved=[];
w.HTMLMediaElement.prototype.load=()=>{};w.HTMLMediaElement.prototype.pause=()=>{};
w.setInterval=()=>1;w.clearInterval=()=>{};
w.URL.createObjectURL=()=> 'blob:http://localhost/result';w.URL.revokeObjectURL=()=>{};
const nativeClick=w.HTMLAnchorElement.prototype.click;
w.HTMLAnchorElement.prototype.click=function(){if(this.href.startsWith('blob:'))saved.push(this.download);else nativeClick.call(this);};
w.eval(fs.readFileSync('web/js/minimax_preview.js','utf8').replace('export function','function'));
const api={apiURL:p=>p,fetchApi:async(path,options)=>{
 if(path.endsWith('/preview/info')){const body=JSON.parse(options.body);return {ok:true,json:async()=>({found:true,key:revision+'-'+body.scope,scope:body.scope,project_id:'project',label:'Current clip'})};}
 if(path.includes('download=1')){
  requests.push(path);if(held)await new Promise(r=>release=r);
  if(fail)return {ok:false,status:503,json:async()=>({error:'Export unavailable'})};
  return {ok:true,headers:{get:()=> 'video/mp4'},blob:async()=>new w.Blob(['mp4'])};
 }
 return {ok:true,clone(){return this;},blob:async()=>new w.Blob(['mp4'])};
}};
let options={};const root=w.document.querySelector('#root');
const player=w.installSmartPreview({root,toolbar:w.document.createElement('div'),timelinePanel:w.document.createElement('div'),inspector:w.document.createElement('div'),node:{id:1},api,getTimeline:()=>({project_id:'project'}),getOptions:()=>options,saveOptions:o=>options=o,standalone:true});
const tick=()=>new Promise(r=>setTimeout(r,0));const settle=async()=>{for(let i=0;i<6;i++)await tick();};
(async()=>{
 await settle();const button=root.querySelector('a'),selector=root.querySelector('select');
 held=true;button.click();await settle();assert.equal(button.textContent,'Preparing download…');
 button.click();assert.equal(requests.length,1,'Duplicate clicks share one download');
 scope='full';selector.value=scope;selector.onchange();await settle();revision='two';await player.refresh();await settle();
 release();held=false;await settle();
 assert(saved[0].includes('latest-clip-one-late'),'Download captures the displayed clip, despite later scope/revision changes');
 assert(requests[0].includes('key=one-latest'));
 button.click();await settle();assert(saved[1].includes('full-video-two-full'));
 fail=true;button.click();await settle();assert(root.querySelector('.mmx-preview-status').textContent.includes('Export unavailable'));
 assert.equal(button.textContent,'Save preview');assert(!button.hasAttribute('aria-busy'));
 player.dispose();dom.window.close();console.log('Preview downloads passed: current revision, latest/full, progress, duplicate prevention and errors.');
})().catch(error=>{console.error(error);player.dispose();dom.window.close();process.exitCode=1;});
