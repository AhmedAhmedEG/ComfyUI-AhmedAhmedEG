const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),crypto=require('crypto');
const events=new Map(),progress=[];let latest,mode='success';
class FakeXHR {
 constructor(){this.upload={};this.headers={};latest=this;}
 open(method,url){this.url=url;}
 setRequestHeader(k,v){this.headers[k]=v;}
 abort(){this.onabort();}
 send(body){this.body=body;if(mode==='pending')return;queueMicrotask(()=>{
  this.upload.onprogress({loaded:5,total:10,lengthComputable:true});this.upload.onload();
  const id=new URL('http://local'+this.url).searchParams.get('job_id');events.get('minimax_transfer')?.({detail:{job_id:id,phase:'Extracting media',done:8,total:10}});
  this.onprogress({loaded:10,total:10,lengthComputable:true});this.status=mode==='error'?400:200;this.response=new Blob([mode==='error'?'{"error":"Bad archive"}':'{"timeline":{"clips":[]}}']);this.onload();
 });}
}
const context={api:{apiURL:u=>u,addEventListener:(n,f)=>events.set(n,f),removeEventListener:n=>events.delete(n)},crypto,XMLHttpRequest:FakeXHR,FormData,Blob,DOMException,AbortController,Promise,URL,console};
vm.createContext(context);vm.runInContext(fs.readFileSync('web/js/minimax_transfer.js','utf8').replace(/^import .*;\r?\n/gm,'').replaceAll('export function','function'),context);
(async()=>{
 const result=await context.transferRequest('/convert',{body:{project:'fixture'},onProgress:e=>progress.push(e)});
 assert.equal(result.timeline.clips.length,0);assert(progress.some(e=>e.phase==='Uploading'&&e.done===5));assert(progress.some(e=>e.phase==='Extracting media'&&e.done===8));assert(progress.some(e=>e.phase==='Downloading'&&e.total===10));assert.equal(events.size,0);assert.equal(latest.headers['Content-Type'],'application/json');
 mode='error';await assert.rejects(context.transferRequest('/convert',{body:{}}),/Bad archive/);assert.equal(events.size,0);
 mode='pending';const controller=new AbortController(),pending=context.transferRequest('/convert',{body:new FormData(),signal:controller.signal});controller.abort();await assert.rejects(pending,e=>e.name==='AbortError');assert.equal(events.size,0);assert.equal(latest.headers['Content-Type'],undefined);
 console.log('Transfer UI: upload, server extraction, download progress, errors, cancellation and listener cleanup passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
