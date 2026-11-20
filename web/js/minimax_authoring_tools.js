import {app} from "../../scripts/app.js";
import {api} from "../../scripts/api.js";
import {peopleEditor} from "./minimax_people.js";
import {transferRequest,transferLabel} from "./minimax_transfer.js";

const widget=(node,name)=>node.widgets?.find(w=>w.name===name);
const value=(node,name,fallback="")=>widget(node,name)?.value ?? fallback;
const referenceRoles=ref=>Array.isArray(ref.roles)?ref.roles:String(ref.forge_kinds || ref.role || 'subject').split(',').map(v=>v.trim()==='subject'?'character':v.trim()).filter(Boolean);
const nodes=()=> (app.rootGraph || app.graph)?._nodes || [];
const masters=()=>nodes().filter(n=>["MiniMaxH3MasterNode","MiniMaxH3MasterDirector"].includes(n.comfyClass || n.type));
const state=node=>JSON.parse(value(node,"timeline_data","{}"));
function persist(node,name,data){const w=widget(node,name);if(!w)throw Error(`Missing ${name}`);w.value=JSON.stringify(data);w.callback?.(w.value);app.graph?.setDirtyCanvas(true,true);}
function widgetVisibility(w,hidden){
  Object.assign(w.options ||= {},{hidden});w.hidden=hidden;
  // Frontend 1.51's BaseWidget keeps a separate reactive options snapshot.
  // Newer frontends synchronize it through the public facade; this guarded
  // legacy fallback updates the snapshot without importing internal stores.
  const legacy=w._state;if(legacy && legacy.options && 'type' in legacy && 'value' in legacy)legacy.options={...legacy.options,hidden};
}
function hide(node,name){const w=widget(node,name);if(w){widgetVisibility(w,true);w.type="hidden";w.computeSize=()=>[0,-4];
  const el=w.element || w.inputEl;if(el){w.__mmxDOMVisibility ||= {hidden:el.hidden,display:el.style.getPropertyValue('display'),priority:el.style.getPropertyPriority('display')};el.hidden=true;el.style.setProperty('display','none','important');}
}}
function syncOutputLabels(node){
  const type=node.comfyClass || node.type;
  if(type==='MiniMaxH3MasterNode' && node.outputs?.[2]?.type==='VHS_VIDEOINFO'){
    const port=node.outputs[2];port.name='video_info';if(port.label==='video')port.label='video_info';
  }
  if(type==='MiniMaxH3ApplyPromptDraft' && node.outputs){
    if(node.outputs.length===1 && node.outputs[0].type==='STRING')node.addOutput?.('timeline','MMX_TIMELINE');
    if(node.outputs[0]?.name==='STRING')node.outputs[0].name='timeline_json';
  }
}
function viewURL(filename){const parts=filename.replaceAll('\\','/').split('/');return api.apiURL('/view?'+new URLSearchParams({filename:parts.pop(),subfolder:parts.join('/'),type:'input'}));}
function conditionalWidgets(node){
  let visibilityChanged=false;
  const saved=new Map();for(const w of node.widgets || [])saved.set(w,{type:w.type,computeSize:w.computeSize});
  const show=(name,visible)=>{const w=widget(node,name),old=saved.get(w);if(!w || !old)return;visibilityChanged ||= (w.options?.hidden ?? false)!==!visible;if(visible){w.type=old.type;widgetVisibility(w,false);w.computeSize=old.computeSize;
    const el=w.element || w.inputEl,dom=w.__mmxDOMVisibility;if(el && dom){el.hidden=dom.hidden;if(dom.display)el.style.setProperty('display',dom.display,dom.priority);else el.style.removeProperty('display');}
  }else hide(node,name);};
  const update=()=>{const type=node.comfyClass || node.type;
    visibilityChanged=false;
    if(type==='MiniMaxH3DirectorSettings'){
      const policy=value(node,'canvas_policy','manual');
      for(const name of ['width','height'])show(name,policy==='manual');
      for(const name of ['canvas_megapixels','canvas_aspect'])show(name,policy==='auto');
    }
    if(type==='MiniMaxH3DirectorSelfLift'){
      const transition=value(node,'split_mode','highres_steps')==='transition_step';
      show('highres_steps',!transition);show('transition_step',transition);
      for(const name of ['tile_count','tile_overlap'])show(name,!!value(node,'enable_tiling',false));
    }
    if(type==='MiniMaxH3LocalPromptModel')show('projection',value(node,'backend','transformers')==='gguf' && !!value(node,'vision',false));
    if(type==='MiniMaxH3DirectorRefine'){
      const upscale=value(node,'mode')!=='refine',latent=value(node,'upscale_method','latent')==='latent',sampling=value(node,'mode')!=='latent_upscale',global=value(node,'backend','global')==='global';
      for(const name of ['target_width','target_height','upscale_method'])show(name,upscale);
      const follow=value(node,'canvas_policy','manual')==='follow';show('canvas_policy',upscale);show('megapixels',upscale && follow);
      show('target_width',upscale && !follow);show('target_height',upscale && !follow);
      show('refine_seed',sampling && value(node,'seed_policy','legacy')==='independent');show('seed_after_generate',sampling && value(node,'seed_policy','legacy')==='independent');show('seed_policy',sampling);
      show('resize_method',upscale && !latent);
      for(const name of ['latent_upscale_model','enable_latent_chunking','upscale_precision'])show(name,(upscale || global) && latent);
      const learned=(upscale || global) && latent && value(node,'latent_upscale_model','interpolate')!=='interpolate';show('spike_guard',learned);
      for(const name of ['guard_sensitivity','guard_strength','guard_mode'])show(name,learned && !!value(node,'spike_guard',false));
      for(const name of ['steps','denoise','sampler','scheduler','passes','enable_tiling'])show(name,sampling);
      for(const name of ['tile_count','tile_overlap'])show(name,sampling && !global && !!value(node,'enable_tiling',false));show('memory_budget_mb',global);show('memory_planning',global);show('memory_reserve_pct',global && !!value(node,'memory_planning',true));
    }
    if(type==='MiniMaxH3FrameInterpolation')show('quality',value(node,'provider','Linear')==='RTX');
    if(type==='MiniMaxH3PixelUpscale')for(const name of ['quality','denoise','deblur'])show(name,value(node,'provider','bicubic').startsWith('RTX'));
    if(type==='MiniMaxH3PromptForge'){
      const backend=value(node,'backend','local'),linked=node.inputs?.some(i=>i.name==='generator' && i.link!=null);
      show('endpoint',backend!=='local');show('model_name',!linked);
      if(node.__mmxSessionKey)node.__mmxSessionKey.closest('label').hidden=backend==='local';
      for(const name of ['timeline','shot_descriptions','continuation_clip_id','api_key'])hide(node,name);
    }
    if(type==='MiniMaxH3ProjectVideo'){const picking=value(node,'selection','all')==='clip_ids';show('clip_ids',picking);show('authoring_tools',picking);show('refine_pass',value(node,'stream','final')==='refine_pass');}
    // Nodes 2.0 snapshots display metadata from its shallow-reactive widget
    // array. Invalidate that snapshot only on a visibility transition, keeping
    // the same widget objects and their final serialized order.
    if(visibilityChanged && node.widgets?.length){const first=node.widgets.shift();node.widgets.unshift(first);}
    if(visibilityChanged && (!node.__mmxTools || type==='MiniMaxH3ProjectVideo'))queueMicrotask(()=>{const minimum=node.computeSize?.();if(minimum)node.setSize?.([node.size?.[0] || minimum[0],minimum[1]]);});
    node.setDirtyCanvas?.(true,true);
  };
  const controls=new Set(['mode','upscale_method','canvas_policy','seed_policy','latent_upscale_model','spike_guard','enable_tiling','memory_planning','provider','selection','stream','backend','shot_count','split_mode','vision']);
  for(const w of node.widgets || []){const old=w.callback;w.callback=function(...args){if(controls.has(w.name) && args[0]!==undefined)w.value=args[0];const result=old?.apply(this,args);update();return result;};}
  node.__mmxUpdateVisibility=update;update();
}
function element(tag,text,className){const e=document.createElement(tag);if(text)e.textContent=text;if(className)e.className=className;return e;}
function field(root,label,input){const row=element("label",label,"mmx-tool-field");row.append(input);root.append(row);return input;}
function input(root,label,type,current,change){const e=document.createElement("input");e.type=type;e.value=current ?? "";e.onchange=()=>change(e.value);return field(root,label,e);}
// Graphical crop: drag inside the box to move it, drag a handle to resize it,
// drag outside it to draw a new one. Values stay normalized (0..1) for the
// backend's edit_images(). The DOM is updated live; settings save on release.
const CROP_ASPECTS=[['free','Free'],['source','Original'],['16:9','16:9'],['9:16','9:16'],['1:1','1:1'],['4:3','4:3'],['3:4','3:4']];
const CROP_MIN=.02;
function cropEditor(node,media,a,save,details,type){
  const stage=element('div',null,'mmx-crop-stage');media.replaceWith(stage);stage.append(media);
  const layer=element('div',null,'mmx-crop-layer'),frame=element('div',null,'mmx-crop-box');
  layer.append(frame);stage.append(layer);
  for(const h of ['nw','n','ne','e','se','s','sw','w']){const d=element('span',null,'mmx-crop-handle');d.dataset.handle=h;frame.append(d);}
  let crop={x:0,y:0,width:1,height:1,...(a.crop || {})};
  const natural=()=>{const w=media.naturalWidth || media.videoWidth || 0,h=media.naturalHeight || media.videoHeight || 0;return w && h?[w,h]:null;};
  // Normalized width/height ratio for a pixel aspect ratio on this source.
  const normalizedAspect=()=>{
    const mode=a.crop_aspect || 'free';if(mode==='free')return null;
    const size=natural();const [W,H]=size || [1,1];
    if(mode==='source')return 1;
    const [rw,rh]=mode.split(':').map(Number);return (rw/rh)*H/W;
  };
  const clamp=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));
  const tools=element('div',null,'mmx-crop-tools');details.append(tools);
  const aspect=choice(tools,'Aspect',CROP_ASPECTS,a.crop_aspect || 'free',v=>{
    if(v==='free')delete a.crop_aspect;else a.crop_aspect=v;
    const r=normalizedAspect();
    if(r){const cx=crop.x+crop.width/2,cy=crop.y+crop.height/2;let h=crop.height,w=h*r;
      if(w>1){w=1;h=w/r;}if(h>1){h=1;w=h*r;}
      crop={width:w,height:h,x:clamp(cx-w/2,0,1-w),y:clamp(cy-h/2,0,1-h)};}
    render();commit();
  });
  const readout=element('span',null,'mmx-crop-readout');tools.append(readout);
  const reset=element('button','Reset Crop');reset.type='button';reset.onclick=()=>{crop={x:0,y:0,width:1,height:1};render();commit();};tools.append(reset);
  details.append(element('p',type==='video'?'Open this section to drag the crop box over the video. Drag inside to move, drag the handles to resize, drag outside to draw a new box.':'Drag inside the box to move it, drag the handles to resize, or drag outside it to draw a new box.','mmx-role-help'));
  const isFull=()=>crop.x<=.0005 && crop.y<=.0005 && crop.width>=.9995 && crop.height>=.9995;
  const render=()=>{
    Object.assign(frame.style,{left:crop.x*100+'%',top:crop.y*100+'%',width:crop.width*100+'%',height:crop.height*100+'%'});
    stage.classList.toggle('mmx-crop-full',isFull());
    const size=natural();
    readout.textContent=isFull()?'Full frame':size?`${Math.round(crop.width*size[0])}×${Math.round(crop.height*size[1])} px`:`${Math.round(crop.width*100)}% × ${Math.round(crop.height*100)}%`;
  };
  const commit=()=>{
    if(isFull())delete a.crop;
    else{
      const r=v=>Math.round(v*10000)/10000;
      const x=r(crop.x),y=r(crop.y);
      a.crop={x,y,width:Math.min(r(crop.width),1-x),height:Math.min(r(crop.height),1-y)};
    }
    save();
  };
  // Opposite corner stays fixed; the pointer defines the other corner.
  const fromAnchor=(ax,ay,px,py,r)=>{
    const sx=px>=ax?1:-1,sy=py>=ay?1:-1;let w=Math.abs(px-ax),h=Math.abs(py-ay);
    const maxW=sx>0?1-ax:ax,maxH=sy>0?1-ay:ay;
    if(r){if(w/Math.max(h,1e-9)>r)h=w/r;else w=h*r;const s=Math.min(1,maxW/Math.max(w,1e-9),maxH/Math.max(h,1e-9));w*=s;h*=s;}
    else{w=Math.min(w,maxW);h=Math.min(h,maxH);}
    return {x:sx>0?ax:ax-w,y:sy>0?ay:ay-h,width:w,height:h};
  };
  const point=e=>{const b=layer.getBoundingClientRect();return [clamp((e.clientX-b.left)/(b.width || 1),0,1),clamp((e.clientY-b.top)/(b.height || 1),0,1)];};
  let drag=null;
  layer.onpointerdown=e=>{
    if(e.button!==undefined && e.button!==0)return;
    const [px,py]=point(e),handle=e.target?.dataset?.handle;
    const start={...crop};
    if(handle)drag={mode:'resize',handle,start};
    else if(e.target===frame && !isFull())drag={mode:'move',start,px,py};
    else drag={mode:'draw',ax:px,ay:py,start};
    layer.setPointerCapture?.(e.pointerId);e.preventDefault();e.stopPropagation?.();
  };
  layer.onpointermove=e=>{
    if(!drag)return;
    const [px,py]=point(e),r=normalizedAspect(),s=drag.start;
    if(drag.mode==='move'){crop={...s,x:clamp(s.x+px-drag.px,0,1-s.width),y:clamp(s.y+py-drag.py,0,1-s.height)};}
    else if(drag.mode==='draw'){crop=fromAnchor(drag.ax,drag.ay,px,py,r);}
    else{
      const h=drag.handle,right=s.x+s.width,bottom=s.y+s.height;
      if(h.length===2){ // corner: anchor the opposite corner
        crop=fromAnchor(h.includes('w')?right:s.x,h.includes('n')?bottom:s.y,px,py,r);
      }else if(h==='e' || h==='w'){
        let x0=h==='e'?s.x:clamp(px,0,right-CROP_MIN),x1=h==='e'?clamp(px,s.x+CROP_MIN,1):right,w=x1-x0;
        if(r){const cy=s.y+s.height/2;let hh=w/r;const maxH=2*Math.min(cy,1-cy);if(hh>maxH){hh=maxH;w=hh*r;if(h==='w')x0=x1-w;}crop={x:x0,y:cy-hh/2,width:w,height:hh};}
        else crop={...s,x:x0,width:w};
      }else{
        let y0=h==='s'?s.y:clamp(py,0,bottom-CROP_MIN),y1=h==='s'?clamp(py,s.y+CROP_MIN,1):bottom,hh=y1-y0;
        if(r){const cx=s.x+s.width/2;let w=hh*r;const maxW=2*Math.min(cx,1-cx);if(w>maxW){w=maxW;hh=w/r;if(h==='n')y0=y1-hh;}crop={x:cx-w/2,y:y0,width:w,height:hh};}
        else crop={...s,y:y0,height:hh};
      }
    }
    render();
  };
  layer.onpointerup=layer.onpointercancel=e=>{
    if(!drag)return;
    if(e && e.type!=='pointercancel')layer.onpointermove(e);
    const mode=drag.mode,start=drag.start;drag=null;layer.releasePointerCapture?.(e?.pointerId);
    // A click without a real drag never replaces the existing crop.
    if(crop.width<CROP_MIN || crop.height<CROP_MIN){crop=start;render();return;}
    if(mode==='draw' && crop.width===start.width && crop.height===start.height && crop.x===start.x && crop.y===start.y)return;
    commit();
  };
  // Videos keep their native controls usable until the Crop section is open.
  const setActive=()=>{const active=type!=='video' || details.open;layer.classList.toggle('mmx-crop-active',active);if(type==='video')media.controls=!details.open;};
  details.open=node.properties.mmx_crop_open===true;
  details.addEventListener('toggle',()=>{node.properties.mmx_crop_open=details.open;setActive();});
  media.addEventListener?.(type==='video'?'loadedmetadata':'load',()=>{render();});
  aspect.value=a.crop_aspect || 'free';
  setActive();render();
  return {stage,layer,frame,get crop(){return {...crop};}};
}
function choice(root,label,options,current,change){const e=document.createElement("select");for(const [v,t] of options.map(o=>Array.isArray(o)?o:[o,o])){const x=element("option",t);x.value=v;e.append(x);}e.value=current;e.onchange=()=>change(e.value);return field(root,label,e);}
function button(root,label,action){const b=element("button",label);b.onclick=async()=>{b.disabled=true;try{await action();}catch(e){const status=root.__status || root.closest('.mmx-authoring-tool')?.__status;if(status){status.textContent=e.message;status.dataset.error="true";}}finally{b.disabled=false;}};root.append(b);return b;}
async function request(path,body,signal){const r=await api.fetchApi(path,{method:body===undefined?"GET":"POST",headers:body===undefined?{}:{"Content-Type":"application/json"},body:body===undefined?undefined:JSON.stringify(body),signal});const data=await r.json();if(!r.ok)throw Error(data.error || `HTTP ${r.status}`);return data;}
function mount(node,title){if(node.__mmxTools)return node.__mmxTools;const root=element("div",null,"mmx-authoring-tool");root.append(element("h3",title));root.__status=element("p","Ready","mmx-tool-status");root.append(root.__status);for(const event of ["pointerdown","mousedown","wheel"])root.addEventListener(event,e=>e.stopPropagation());node.addDOMWidget("authoring_tools","MMX_TOOLS",root,{serialize:false}).computeSize=()=>[580,500];node.size=[Math.max(600,node.size?.[0]||0),Math.max(650,node.size?.[1]||0)];node.__mmxTools=root;return root;}
function panelHeight(node,height){const w=widget(node,'authoring_tools');if(!w || w.__mmxHeight===height)return;w.__mmxHeight=height;w.computeSize=()=>[580,height];queueMicrotask(()=>{const minimum=node.computeSize?.();if(minimum)node.setSize?.([Math.max(600,node.size?.[0] || 0),minimum[1]]);});}
function masterPicker(root,node){const picker=field(root,"Master",document.createElement("select"));const refresh=()=>{picker.replaceChildren();const found=masters();if(!found.length){const o=element("option","No Master node in this workflow");o.value="";o.disabled=true;picker.append(o);}for(const n of found){const o=element("option",`${n.title || "Master"} · ${n.id}`);o.value=n.id;picker.append(o);}picker.value=node.properties.mmx_target || picker.options[0]?.value;};refresh();picker.onchange=()=>{node.properties.mmx_target=picker.value;root.__mmxMasterChanged?.();};button(root,"Refresh Masters",()=>{refresh();root.__mmxMasterChanged?.();});return ()=>{const master=masters().find(n=>String(n.id)===picker.value);if(!master)throw Error("Choose a Master in this workflow.");return master;};}

function providerOptions(node,key='') {
  const socket=node.inputs?.find(i=>i.name==='generator'),link=(node.graph || app.graph)?.links?.[socket?.link];
  const provider=link && (node.graph || app.graph).getNodeById(Array.isArray(link)?link[1]:link.origin_id);
  return {backend:value(node,'backend','ollama'),endpoint:value(node,'endpoint','http://localhost:11434'),model:provider?value(provider,'model_name'):value(node,'model_name'),api_key:key || value(node,'api_key'),local_backend:provider?value(provider,'backend','transformers'):'transformers',lifetime:provider?value(provider,'lifetime','unload_after_draft'):'unload_after_draft',context_length:provider?Number(value(provider,'context_length',8192)):8192,device:provider?value(provider,'device','cpu'):'cpu',projection:provider?value(provider,'projection'):''};
}
async function visionRequest(node,options,body) {
  if(node.__mmxVisionJob)throw Error('Wait for or cancel the current vision request.');
  const controller=new AbortController(),id=crypto.randomUUID();node.__mmxVisionJob={id,controller};
  try{return await request('/minimax_director/forge/vision',{...options,...body,job_id:id},controller.signal);}
  finally{if(node.__mmxVisionJob?.id===id)node.__mmxVisionJob=null;}
}
async function cancelVision(node) {const job=node.__mmxVisionJob;if(job){job.controller.abort();node.__mmxVisionJob=null;await request('/minimax_director/forge/cancel',{job_id:job.id});}}
function castPanel(node,root,getMaster,options) {
  const details=element('details');details.append(element('summary','Cast Appearance Cards'));root.append(details);
  details.append(element('p','Read selected reference pictures, review the description, then use it. Manual corrections stay authoritative.'));
  const picker=choice(details,'Cast Card',[],'',()=>draw());const text=field(details,'Reviewed Appearance',document.createElement('textarea'));text.rows=6;
  const refresh=()=>{const old=picker.value;picker.replaceChildren();let timeline;try{timeline=state(getMaster());}catch{return;}
    const ids=new Set([...(timeline.shared_ref_ids || []),...(timeline.clips || []).flatMap(c=>c.ref_ids || [])]);const keys=new Map();
    for(const ref of [...(timeline.references || []),...(timeline.available_refs || [])])if(ids.has(ref.id) && ref.type==='image' && ref.forge_include!==false){
      const numbers=Array.isArray(ref.characters)?ref.characters:String(ref.characters || '').split(',').filter(Boolean);
      for(const n of [...numbers,...(ref.boxes || []).map(b=>b.n)])keys.set(String(n),`Character ${n}`);
      for(const role of referenceRoles(ref)){if(['place','style'].includes(role))keys.set(role,role==='place'?'Place':'Style');if(role==='pose')keys.set('pose:'+ref.id,'Pose · '+(ref.name || ref.id));}
    }
    for(const key of Object.keys(timeline.cast_cards || {}))if(!keys.has(key))keys.set(key,key);
    for(const [key,label] of keys){const o=element('option',label);o.value=key;picker.append(o);}picker.value=keys.has(old)?old:picker.options[0]?.value || '';draw();};
  function draw(){let timeline;try{timeline=state(getMaster());}catch{return;}text.value=timeline.cast_cards?.[picker.value] || '';picker.disabled=!picker.options.length;}
  button(details,'Refresh Cast Cards',refresh);
  button(details,'Read Card From Pictures',async()=>{if(!picker.value)throw Error('Assign image references and character numbers or a place/style/pose role first.');const key=picker.value;root.__status.textContent='Reading cast pictures…';const result=await visionRequest(node,options(),{operation:'describe',timeline:state(getMaster()),card_key:key,instruction:text.value});if(picker.value===key)text.value=result.text;root.__status.textContent='Description Ready · Review Before Using';});
  button(details,'Use Reviewed Description',()=>{if(!picker.value)throw Error('Choose a cast card.');const master=getMaster(),timeline=state(master);timeline.cast_cards ||= {};if(text.value.trim())timeline.cast_cards[picker.value]=text.value.trim();else delete timeline.cast_cards[picker.value];persist(master,'timeline_data',timeline);master.__mmxDirectorRefresh?.();root.__status.textContent='Reviewed Cast Card Saved';});
  button(details,'Cancel Vision Request',()=>cancelVision(node));refresh();return refresh;
}

function forge(node){for(const name of ['timeline','shot_descriptions','continuation_clip_id','api_key'])hide(node,name);const root=mount(node,"Prompt Forge · Draft And Review");root.classList.add('mmx-forge-editor');const getMaster=masterPicker(root,node);let controller=null,sequence=0,draft=null,jobId=null;
  const editor=field(root,"Review Draft JSON",document.createElement("textarea"));editor.rows=8;editor.placeholder="Generate a draft, review its prompts, then Apply.";
  const history=choice(root,"Draft History",[],"",index=>{draft=node.properties.mmx_draft_history?.[Number(index)];if(draft)editor.value=JSON.stringify(draft,null,2);});
  const updateHistory=()=>{history.replaceChildren();(node.properties.mmx_draft_history || []).forEach((d,i)=>{const o=element("option",`${i+1} · ${d.count} Clips`);o.value=i;history.append(o);});};updateHistory();node.__mmxReload=updateHistory;
  const key=input(root,"Session API Key","password","",()=>{});key.autocomplete="off";
  node.__mmxSessionKey=key;
  node.__mmxVisionOptions=()=>providerOptions(node,key.value);
  const refreshCast=castPanel(node,root,getMaster,node.__mmxVisionOptions);
  const vision=document.createElement('input');vision.type='checkbox';vision.checked=!!node.properties.mmx_vision;field(root,'Send Reference Pictures',vision);vision.onchange=()=>node.properties.mmx_vision=vision.checked;
  const policy=choice(root,"Apply Policy",["replace","append"],"replace",()=>{});
  const imported=element('details');imported.append(element('summary','Imported Prompt History'));root.append(imported);
  const importedPicker=choice(imported,'Archived Prompt',[],'',()=>{});
  button(imported,'Refresh Imported History',()=>{importedPicker.replaceChildren();for(const [i,row] of (state(getMaster()).imported_prompt_history || []).entries()){const o=element('option',`${i+1} · ${row.type} · ${row.prompt.slice(0,60)}`);o.value=String(i);importedPicker.append(o);}});
  button(imported,'Prepare Imported Prompt For Review',async()=>{if(!importedPicker.options.length)throw Error('Refresh imported history first.');const result=await request('/minimax_director/forge/prepare_history',{timeline:state(getMaster()),index:Number(importedPicker.value)});draft=result;editor.value=JSON.stringify(result,null,2);root.__status.textContent='Imported Text Ready · Review Reference Tags And Apply Policy Before Applying';});

  const continuation=choice(root,'Continuation Clip',[],value(node,'continuation_clip_id',''),v=>{const w=widget(node,'continuation_clip_id');if(w){w.value=v;w.callback?.(v);}});
  const descriptionRows=element('div');root.append(descriptionRows);
  const refreshInputs=()=>{
    const selected=value(node,'continuation_clip_id','');continuation.replaceChildren();const independent=element('option','No Tail Context');independent.value='';continuation.append(independent);
    try{for(const clip of state(getMaster()).clips.slice(1)){const o=element('option',clip.name || clip.id);o.value=clip.id;continuation.append(o);}}catch{}
    continuation.value=selected;
    const descriptions=JSON.parse(value(node,'shot_descriptions','[]'));descriptionRows.replaceChildren();
    for(let i=0;i<Number(value(node,'shot_count',1));i++){
      const text=document.createElement('textarea');text.rows=2;text.value=descriptions[i] || '';field(descriptionRows,`Clip ${i+1} Instructions`,text);
      text.onchange=()=>{descriptions[i]=text.value;persist(node,'shot_descriptions',descriptions);};
    }
  };
  root.__mmxMasterChanged=()=>{refreshInputs();refreshCast();};button(root,'Refresh Clip Instructions',refreshInputs);refreshInputs();
  const countWidget=widget(node,'shot_count');if(countWidget){const old=countWidget.callback;countWidget.callback=function(...args){const r=old?.apply(this,args);refreshInputs();return r;};}
  const graphInput=element('details');graphInput.append(element('summary','Advanced Graph Input'));root.append(graphInput);
  graphInput.append(element('p','Used only when running this node through the graph. Interactive draft and review use the selected Master. Connect the reviewed typed timeline output to a downstream Master; avoid a graph cycle.'));
  const graphTimeline=field(graphInput,'Graph Timeline JSON',document.createElement('textarea'));graphTimeline.rows=4;graphTimeline.value=value(node,'timeline','{"clips":[]}');graphTimeline.onchange=()=>{const w=widget(node,'timeline');if(w){w.value=graphTimeline.value;w.callback?.(w.value);}};
  node.__mmxReload=()=>{updateHistory();refreshInputs();refreshCast();graphTimeline.value=value(node,'timeline','{"clips":[]}');};
  const connections=node.onConnectionsChange;node.onConnectionsChange=function(...args){const r=connections?.apply(this,args);node.__mmxUpdateVisibility?.();return r;};

  button(root,"Create Draft",async()=>{const master=getMaster();const timeline=state(master);const epoch=++sequence;controller?.abort();controller=new AbortController();jobId=crypto.randomUUID();root.__status.textContent="Generating Draft…";
    const descriptions=JSON.parse(value(node,"shot_descriptions","[]"));
    const generatorInput=node.inputs?.find(i=>i.name==='generator');const link=app.graph?.links?.[generatorInput?.link];const provider=link && app.graph.getNodeById(link.origin_id);
    const result=await request('/minimax_director/forge/draft',{job_id:jobId,timeline,instruction:value(node,"instruction"),count:Number(value(node,"shot_count",1)),backend:value(node,"backend","ollama"),endpoint:value(node,"endpoint"),model:provider?value(provider,"model_name"):value(node,"model_name"),local_backend:provider?value(provider,"backend","transformers"):"transformers",lifetime:provider?value(provider,"lifetime","unload_after_draft"):"unload_after_draft",context_length:provider?Number(value(provider,"context_length",8192)):8192,continuation_clip_id:continuation.value,device:provider?value(provider,"device","cpu"):"cpu",projection:provider?value(provider,"projection"):"",vision_ids:vision.checked?[...(timeline.references || []),...(timeline.available_refs || [])].filter(r=>r.filename && ['image','video'].includes(r.type) && r.forge_include!==false).slice(0,12).map(r=>r.id):[],api_key:key.value || value(node,"api_key"),creativity:Number(value(node,"creativity",4)),detail:Number(value(node,"detail",6)),shot_descriptions:descriptions},controller.signal);
    if(epoch!==sequence)return;jobId=null;draft=result;editor.value=JSON.stringify(result,null,2);node.properties.mmx_draft_history=[result,...(node.properties.mmx_draft_history || [])].slice(0,3);updateHistory();root.__status.textContent="Draft Ready · Review Before Applying";
  });
  button(root,"Cancel Request",async()=>{sequence++;const pending=jobId;jobId=null;controller?.abort();if(pending)await request("/minimax_director/forge/cancel",{job_id:pending});root.__status.textContent="Draft Cancelled · No Draft Applied";});
  button(root,"Apply Reviewed Draft",async()=>{const master=getMaster();if(master.inputs?.some(i=>i.name==='timeline' && i.link!=null))throw Error("Timeline Builder owns this Master. Apply changes to the builder's groups instead.");const reviewed=JSON.parse(editor.value);const result=await request('/minimax_director/forge/apply',{timeline:state(master),draft:reviewed,policy:policy.value});persist(master,'timeline_data',result.timeline);master.__mmxDirectorRefresh?.();root.__status.textContent="Reviewed Draft Applied";});
  button(root,"Clear Draft History",()=>{node.properties.mmx_draft_history=[];updateHistory();editor.value="";});
  const removed=node.onRemoved;node.onRemoved=function(...args){if(jobId)void request("/minimax_director/forge/cancel",{job_id:jobId}).catch(()=>{});controller?.abort();sequence++;return removed?.apply(this,args);};
}

function refmods(node){hide(node,'library_data');const root=mount(node,"RefMod Library");const list=element("div");root.append(list);let rows=JSON.parse(value(node,'library_data','[]'));const save=()=>persist(node,'library_data',rows);
  const draw=async()=>{const entries=await request('/minimax_director/refmods');list.replaceChildren();for(const entry of entries){const box=element("fieldset");box.append(element("legend",entry.name));const enabled=document.createElement('input');enabled.type='checkbox';let row=rows.find(r=>r.name===entry.name);enabled.checked=!!row;field(box,'Use RefMod',enabled);enabled.onchange=()=>{if(enabled.checked){row={id:'library_'+crypto.randomUUID(),name:entry.name,description:entry.description || '',strength:1};rows.push(row);}else{rows=rows.filter(r=>r.name!==entry.name);row=null;}save();};
      input(box,'Description','text',row?.description ?? entry.description,v=>{if(!row){enabled.checked=true;row={id:'library_'+crypto.randomUUID(),name:entry.name,strength:1};rows.push(row);}row.description=v;save();});
      const strength=input(box,'Strength','number',row?.strength ?? 1,v=>{if(!row){enabled.checked=true;row={id:'library_'+crypto.randomUUID(),name:entry.name,description:entry.description || ''};rows.push(row);}row.strength=Number(v);save();});strength.min=0;strength.max=4;strength.step=.05;list.append(box);}
    root.__status.textContent=`${entries.length} Installed RefMods`;panelHeight(node,entries.length?500:150);
  };node.__mmxReload=()=>{rows=JSON.parse(value(node,'library_data','[]'));return draw();};button(root,'Refresh Library',draw);void draw().catch(e=>root.__status.textContent=e.message);
}

function assets(node){
  const hideNative=()=>{for(const w of node.widgets || [])if(w.name==='asset_edits' || /^(image|video|audio|refmod)_\d+(_name|_fps)?$/.test(w.name))hide(node,w.name);};hideNative();
  const root=mount(node,"Reference Pack");root.classList.add('mmx-ref-editor');const panelWidget=widget(node,'authoring_tools');if(panelWidget)panelWidget.computeSize=()=>[580,620];let data=JSON.parse(value(node,'asset_edits','{}'));data.assets ||= {};data.files ||= [];const list=element('div');root.append(list);const save=()=>persist(node,'asset_edits',data);
  let selected=node.properties.mmx_asset_selection || '';
  const picker=choice(root,'Edit Reference',[],selected,id=>{selected=id;node.properties.mmx_asset_selection=id;draw();});
  root.insertBefore(picker.parentElement,list);
  const watched=new WeakSet();
  function sourceFilename(slot){
    const graph=node.graph || app.rootGraph || app.graph;
    let current=node.inputs?.find(i=>i.name===slot),origin=null;
    const visited=new Set();
    while(current?.link!=null){
      const link=graph?.links?.[current.link];
      const id=Array.isArray(link)?link[1]:link?.origin_id;
      if(id==null || visited.has(id))return '';
      visited.add(id);origin=graph.getNodeById(id);
      if(!origin)return '';
      if((origin.comfyClass || origin.type)==='Reroute'){current=origin.inputs?.[0];continue;}
      break;
    }
    if(!origin)return '';
    if(!watched.has(origin)){watched.add(origin);for(const w of origin.widgets || []){
      if(!['image','video','audio','filename','file'].includes(w.name))continue;
      const callback=w.callback;w.callback=function(...args){const result=callback?.apply(this,args);draw();return result;};
    }}
    const filename=origin.widgets?.find(w=>['image','video','audio','filename','file'].includes(w.name) && typeof w.value==='string')?.value;
    return filename || '';
  }
  const draw=()=>{list.replaceChildren();const slots=(node.inputs || []).filter(i=>/^(image|video|audio)_\d+$/.test(i.name) && i.link!=null).map(i=>({id:i.name,type:i.name.split('_')[0],filename:sourceFilename(i.name),settings:data.assets[i.name] ||= {}}));for(const f of data.files)slots.push({id:f.id,type:f.type,filename:f.filename,settings:f,file:true});
    panelHeight(node,slots.length?620:220);
    if(!slots.some(a=>a.id===selected))selected=slots[0]?.id || '';
    picker.replaceChildren();for(const asset of slots){const o=element('option',`${asset.id} · ${asset.settings.name || value(node,asset.id+'_name','') || asset.filename || asset.type}`);o.value=asset.id;picker.append(o);}picker.value=selected;picker.disabled=!slots.length;node.properties.mmx_asset_selection=selected;
    for(const asset of slots.filter(a=>a.id===selected)){const a=asset.settings;const box=element('fieldset');box.append(element('legend',asset.id));list.append(box);
      const change=(key,v)=>{a[key]=v;save();};input(box,'Name','text',a.name ?? value(node,asset.id+'_name',''),v=>change('name',v));
      if(asset.type==='image'){
        const roles=element('div',null,'mmx-reference-roles');roles.setAttribute('role','group');roles.setAttribute('aria-label','Reference Roles');roles.append(element('strong','Reference Roles'));box.append(roles);
        const selectedRoles=new Set(referenceRoles(a));
        for(const [key,label] of [['character','Character'],['place','Place'],['style','Style'],['first-frame','First Frame'],['last-frame','Last Frame'],['keyframe','Keyframe'],['pose','Pose'],['custom','Custom']]){
          const toggle=document.createElement('input');toggle.type='checkbox';toggle.checked=selectedRoles.has(key);field(roles,label,toggle);
          toggle.onchange=()=>{if(toggle.checked)selectedRoles.add(key);else selectedRoles.delete(key);if(!selectedRoles.size){selectedRoles.add(key);toggle.checked=true;return;}a.roles=[...selectedRoles];a.role=a.roles[0]==='character'?'subject':['first-frame','last-frame'].includes(a.roles[0])?'keyframe':a.roles[0];save();};
        }
        box.append(element('p','Roles guide prompt writing. The clip type and selected assets determine the model’s actual input frames.','mmx-role-help'));
      }else choice(box,'Role',['subject','place','style','keyframe','pose','custom'],a.role || 'subject',v=>change('role',v));
      input(box,'Description / Instructions','text',a.description || '',v=>change('description',v));
      if(asset.type==='image'){
        const cast=element('details');cast.append(element('summary','Prompt Cast'));box.append(cast);
        const characters=input(cast,'Character Numbers','text',(a.characters || []).join?.(', ') || a.characters || '',v=>change('characters',v.split(',').map(x=>x.trim()).filter(Boolean)));characters.placeholder='1 or 1, 2, 3';
        const mode=document.createElement('input');mode.type='checkbox';mode.checked=node.properties.mmx_people_edit===asset.id;field(cast,'Edit People Boxes',mode);mode.onchange=()=>{node.properties.mmx_people_edit=mode.checked?asset.id:'';draw();};
        const forges=nodes().filter(n=>(n.comfyClass || n.type)==='MiniMaxH3PromptForge');const reader=choice(cast,'Vision Reader',forges.map(n=>[String(n.id),n.title || `Prompt Forge · ${n.id}`]),node.properties.mmx_reader || String(forges[0]?.id || ''),v=>node.properties.mmx_reader=v);
        button(cast,'Find People',async()=>{if(!asset.filename)throw Error('People detection needs a file-backed picture.');const forge=forges.find(n=>String(n.id)===reader.value);if(!forge)throw Error('Add a Prompt Forge node and configure its vision provider.');root.__status.textContent='Finding people…';const result=await visionRequest(node,forge.__mmxVisionOptions?.() || providerOptions(forge),{operation:'find_people',reference:{filename:asset.filename}});node.properties.mmx_pending_people={asset:asset.id,boxes:result.boxes};node.properties.mmx_people_edit=asset.id;draw();root.__status.textContent=`${result.boxes.length} Proposed People · Review Then Use Detected Boxes`;});
        if(node.properties.mmx_pending_people?.asset===asset.id){button(cast,'Use Detected Boxes',()=>{a.boxes=node.properties.mmx_pending_people.boxes.map(b=>({...b,box:[...b.box]}));delete node.properties.mmx_pending_people;save();draw();});button(cast,'Discard Detected Boxes',()=>{delete node.properties.mmx_pending_people;draw();});}
        button(cast,'Cancel Vision Request',()=>cancelVision(node));
        choice(cast,'Position',['unspecified','left','centre','right','left-to-right','top-to-bottom','front-to-back'],a.position || 'unspecified',v=>change('position',v));
        choice(cast,'Retention',['fully_preserved','partially_preserved','attribute_transfer','weak_reference'],a.retention || 'fully_preserved',v=>change('retention',v));
        choice(cast,'Prompt Writer',['Include','Ignore'],a.forge_include===false?'Ignore':'Include',v=>change('forge_include',v==='Include'));
        cast.append(element('p','These guide Prompt Forge. Clip reference selection controls what the video model receives.'));
      }
      let media=null;if(asset.filename){media=document.createElement(asset.type==='image'?'img':asset.type);media.src=viewURL(asset.filename);if(asset.type!=='image')media.controls=true;media.className='mmx-asset-preview';box.append(media);}
      const peopleMode=asset.type==='image' && node.properties.mmx_people_edit===asset.id;
      if(peopleMode && media){const pending=node.properties.mmx_pending_people?.asset===asset.id?node.properties.mmx_pending_people:null;peopleEditor(box,media,pending || a,()=>{if(!pending)save();});}
      if(asset.type==='video' && !asset.file){const slot=node.inputs?.find(i=>i.name===asset.id);const graph=node.graph || app.rootGraph || app.graph;const link=graph?.links?.[slot?.link];const origin=graph?.getNodeById(Array.isArray(link)?link[1]:link?.origin_id);const output=origin?.outputs?.[Array.isArray(link)?link[2]:link?.origin_slot || 0];if(output?.type!=='VIDEO'){const fps=input(box,'Source FPS','number',value(node,asset.id+'_fps',24),v=>{const w=widget(node,asset.id+'_fps');if(w){w.value=Number(v);w.callback?.(w.value);}});fps.min=1;fps.max=240;}}
      if(asset.type!=='image'){
        const start=input(box,'Trim Start (Seconds)','number',a.start || 0,v=>change('start',Number(v)));start.min=0;start.step=1/24;
        const end=input(box,'Trim End (Seconds, Blank = Full)','number',a.end ?? '',v=>change('end',v===''?null:Number(v)));end.min=0;end.step=1/24;
        if(asset.filename){const wave=document.createElement('canvas');wave.width=480;wave.height=60;box.append(wave);request('/minimax_director/media/waveform?'+new URLSearchParams({filename:asset.filename})).then(info=>{const c=wave.getContext('2d');c.fillStyle='#957cce';info.peaks.forEach((peak,i)=>c.fillRect(i*480/info.peaks.length,30-peak*25,2,peak*50));for(const [label,key] of [['Start','start'],['End','end']]){const handle=input(box,`${label} Handle`,'range',key==='start'?(a.start || 0):(a.end ?? info.duration),v=>{change(key,Number(v));(key==='start'?start:end).value=v;});handle.min=0;handle.max=info.duration;handle.step=1/24;}}).catch(()=>{});}
      }
      if(asset.type==='video'){
        choice(box,'Use Video As',[['both','Video + Audio'],['video','Video Only'],['audio','Audio Only'],['frame','Single Frame']],a.media_mode || 'both',v=>{change('media_mode',v);draw();});
        if(a.media_mode==='frame')input(box,'Picked Frame (Seconds After Trim)','number',a.frame_time || 0,v=>change('frame_time',Number(v)));
      }
      if(asset.type!=='audio'){
        const adjustments=element('details');adjustments.className='mmx-asset-adjustments';adjustments.append(element('summary','Color Adjustments'));box.append(adjustments);
        a.edits ||= {};for(const [key,fallback] of [['exposure',0],['contrast',1],['saturation',1]]){const e=input(adjustments,key[0].toUpperCase()+key.slice(1),'number',a.edits[key] ?? fallback,v=>{a.edits[key]=Number(v);save();});e.step=.05;}
        const scaling=element('details');scaling.append(element('summary','Resize'));box.append(scaling);
        const scaleMode=a.scaling || (asset.type==='video'?'Megapixels':'Off');
        choice(scaling,'Scaling',['Off','Megapixels','Target','Fit and pad','Divisible crop'],scaleMode,v=>{change('scaling',v);draw();});
        if(scaleMode==='Megapixels'){
          scaling.open=true;
          const budget=input(scaling,'Input Size (MP)','number',a.megapixels ?? .5,v=>{const n=Number(v);if(!Number.isFinite(n) || n<Number(budget.min) || n>Number(budget.max)){budget.setCustomValidity('Enter a megapixel value within the displayed range.');budget.reportValidity();return;}budget.setCustomValidity('');change('megapixels',n);});
          budget.min='0.001024';budget.max=asset.type==='video'?'1.032192':'16';budget.step='.01';
          scaling.append(element('p','Preserves aspect ratio and aligns to 32 pixels without enlarging smaller sources. 1 MP = 1,000,000 pixels. This prepared reference is used by every clip that selects it.'));
        }else if(scaleMode!=='Off' && scaleMode!=='Divisible crop'){scaling.open=true;input(scaling,'Width','number',a.width || 1344,v=>change('width',Number(v)));input(scaling,'Height','number',a.height || 768,v=>change('height',Number(v)));}
        const cropping=element('details');cropping.append(element('summary','Crop'));box.append(cropping);
        if(media && !peopleMode)cropEditor(node,media,a,save,cropping,asset.type);
        else cropping.append(element('p',media?'Close Edit People Boxes to crop this picture.':'Connect a file-backed source to crop it.','mmx-role-help'));
      }
      if(asset.file)button(box,'Remove Asset',()=>{data.files=data.files.filter(f=>f.id!==asset.id);save();draw();});
    }reset.disabled=!slots.length;root.__status.textContent=`${slots.length} References`;};
  const reset=button(root,'Reset Settings',()=>{const file=data.files.find(f=>f.id===selected);if(file){const identity={id:file.id,type:file.type,filename:file.filename,name:file.name};Object.keys(file).forEach(k=>delete file[k]);Object.assign(file,identity);}else if(selected)data.assets[selected]={};save();draw();});
  node.__mmxReload=()=>{data=JSON.parse(value(node,'asset_edits','{}'));data.assets ||= {};data.files ||= [];hideNative();for(const i of node.inputs || [])if(/^video_\d+$/.test(i.name))i.type='VIDEO,IMAGE';node.widgets_start_y=undefined;const minimum=node.computeSize?.();if(minimum && node.size?.[1]>minimum[1]+160)node.setSize?.([Math.max(600,node.size[0]),minimum[1]]);draw();queueMicrotask(draw);};draw();const original=node.onConnectionsChange;node.onConnectionsChange=function(...args){const result=original?.apply(this,args);hideNative();draw();return result;};
}

function exporter(node){const root=mount(node,'Choose Clips To Export');const getMaster=masterPicker(root,node);const list=element('div');root.append(list);button(root,'Refresh Clips',()=>{const timeline=state(getMaster());const ids=new Set(String(value(node,'clip_ids')).split(',').filter(Boolean));list.replaceChildren();for(const clip of timeline.clips || []){const check=document.createElement('input');check.type='checkbox';check.checked=ids.has(clip.id);field(list,clip.name || clip.id,check);check.onchange=()=>{check.checked?ids.add(clip.id):ids.delete(clip.id);const w=widget(node,'clip_ids');w.value=[...ids].join(',');w.callback?.(w.value);};}root.__status.textContent='Set Selection To clip_ids To Use These Checks';});}

// Shared look for every helper panel (Reference Pack editor, RefMod Library,
// Prompt Forge, Project Import, Export). Matches the Master's project panel:
// system font, card surfaces, labels in one column and controls in another.
const AUTHORING_CSS=`
.mmx-authoring-tool{box-sizing:border-box;height:100%;overflow:auto;padding:12px 14px 14px;background:#1f252b;color:#dbe5ee;border:1px solid #39434d;border-radius:8px;font:13px/1.4 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.mmx-authoring-tool *{box-sizing:border-box}
.mmx-authoring-tool>h3{margin:0 0 2px;font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#8ea2b4}
.mmx-tool-status{display:inline-flex;align-items:center;gap:6px;margin:4px 0 10px;padding:2px 9px;border-radius:10px;font-size:11.5px;color:#8fd6ad;background:#1f3128;border:1px solid #3d6b52}
.mmx-tool-status::before{content:'';width:6px;height:6px;border-radius:50%;background:currentColor}
.mmx-tool-status[data-error=true]{color:#ffc9cf;background:#2a1d21;border-color:#5c3a40}
.mmx-authoring-tool fieldset{margin:10px 0;padding:10px 12px;border:1px solid #39434d;border-radius:8px;background:#1b2026}
.mmx-authoring-tool legend{padding:0 6px;font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:#8ea2b4}
.mmx-authoring-tool details{margin:6px 0;border-top:1px solid #2d363f;padding-top:6px}
.mmx-authoring-tool summary{cursor:pointer;color:#c8d4de;font-weight:600;padding:4px 0}
.mmx-tool-field{display:grid;grid-template-columns:minmax(110px,34%) minmax(0,1fr);align-items:center;gap:10px;margin:6px 0;font-size:12.5px;color:#b9c6d2}
.mmx-tool-field>input[type=checkbox]{justify-self:start;width:16px;height:16px;margin:0;accent-color:#7eafcf}
.mmx-tool-field input:not([type=checkbox]):not([type=range]):not([type=file]),.mmx-tool-field select,.mmx-tool-field textarea{width:100%;min-width:0;height:30px;padding:0 8px;background:#1b2026;color:#e8edf2;border:1px solid #46525e;border-radius:6px;font:inherit}
.mmx-tool-field textarea{height:auto;min-height:72px;padding:6px 8px;resize:vertical;font:12px/1.45 ui-monospace,Consolas,monospace}
.mmx-tool-field input:focus,.mmx-tool-field select:focus,.mmx-tool-field textarea:focus{outline:none;border-color:#7eafcf;box-shadow:0 0 0 2px #7eafcf33}
.mmx-tool-field input[type=file]{width:100%;font-size:12px;color:#9fb2c3}
.mmx-tool-field input[type=file]::file-selector-button{height:28px;margin-right:10px;padding:0 12px;border:1px solid #4b5866;border-radius:6px;background:#2c343d;color:#dfe7ee;font:600 12px system-ui,sans-serif;cursor:pointer}
.mmx-authoring-tool button{display:inline-flex;align-items:center;justify-content:center;height:32px;margin:4px 6px 4px 0;padding:0 14px;background:#2c343d;color:#dfe7ee;border:1px solid #4b5866;border-radius:6px;font:600 12.5px system-ui,sans-serif;cursor:pointer;white-space:nowrap}
.mmx-authoring-tool button:hover:not(:disabled){background:#36414c;border-color:#8ab9df}
.mmx-authoring-tool button:disabled{opacity:.45;cursor:default}
.mmx-authoring-tool pre{max-height:220px;overflow:auto;margin:8px 0;padding:8px 10px;background:#161b20;border:1px solid #2d363f;border-radius:6px;font:11.5px/1.45 ui-monospace,Consolas,monospace;color:#b9c6d2;white-space:pre-wrap;word-break:break-word}
.mmx-authoring-tool pre:empty{display:none}
.mmx-asset-preview{max-width:100%;max-height:220px;display:block;border-radius:6px}
`;
// Fit a newly added helper node to its panel's content instead of a fixed
// 600x650 box. Nodes restored from a workflow keep their saved size.
function fitToContent(node){requestAnimationFrame(()=>{if(node.__mmxConfigured)return;const root=node.__mmxTools,w=widget(node,'authoring_tools');if(!root || !w || !root.isConnected)return;const prev=root.style.height;root.style.height='auto';const natural=Math.ceil(root.scrollHeight)+8;root.style.height=prev;if(w.__mmxHeight || natural<60)return;w.computeSize=()=>[580,natural];const minimum=node.computeSize?.();if(minimum)node.setSize?.([Math.max(600,node.size?.[0] || 0),minimum[1]]);node.setDirtyCanvas?.(true,true);});}
// Reference Pack sockets grew over time (images 5-9, video 3 and audio 3 were
// appended later), so saved nodes list them out of order. Show them grouped:
// images, videos, video soundtracks, audios, RefMods. Execution reads inputs by
// name, so only the drawing order and each link's slot index change.
const PACK_SOCKET_ORDER=['ref_pack_optional',...[1,2,3,4,5,6,7,8,9].map(i=>`image_${i}`),...[1,2,3].map(i=>`video_${i}`),...[1,2,3].map(i=>`video_${i}_audio`),...[1,2,3].map(i=>`audio_${i}`),'refmod_library'];
function sortPackSockets(node){
  const inputs=node.inputs;if(!Array.isArray(inputs) || inputs.length<2)return false;
  const rank=input=>{const i=PACK_SOCKET_ORDER.indexOf(input.name);return i<0?PACK_SOCKET_ORDER.length:i;};
  const sorted=inputs.map((input,i)=>({input,i})).sort((a,b)=>rank(a.input)-rank(b.input) || a.i-b.i).map(row=>row.input);
  if(sorted.every((input,i)=>input===inputs[i]))return false;
  const links=node.graph?.links;
  const link=id=>id==null?null:(typeof links?.get==='function'?links.get(id):links?.[id]);
  inputs.splice(0,inputs.length,...sorted);
  inputs.forEach((input,slot)=>{const row=link(input.link);if(row)row.target_slot=slot;});
  node.setDirtyCanvas?.(true,true);
  return true;
}
function projectImport(node){hide(node,'project_json');const root=mount(node,'Convert Upstream Project');const getMaster=masterPicker(root,node);let converted=null;const report=element('pre');root.append(report);const file=document.createElement('input');file.type='file';file.accept='.json,.zip,.ext';field(root,'Project File',file);const restore=document.createElement('input');restore.type='checkbox';restore.checked=!!node.properties.mmx_restore_cache;field(root,'Restore Compatible Takes',restore);restore.onchange=()=>node.properties.mmx_restore_cache=restore.checked;
 button(root,'Convert And Review',async()=>{if(!file.files[0])throw Error('Choose a project file.');const form=new FormData();form.append('file',file.files[0]);form.append('restore_cache',String(restore.checked));root.__status.textContent='Preparing upload…';const result=await transferRequest('/minimax_director/project/convert',{body:form,onProgress:e=>root.__status.textContent=transferLabel(e)});converted=result.timeline;report.textContent=JSON.stringify(result.report,null,2);const w=widget(node,'project_json');w.value=JSON.stringify(converted);widget(node,'source').value='current';root.__status.textContent='Converted · Review Warnings Before Applying';});
 button(root,'Apply Converted Timeline',()=>{if(!converted)throw Error('Convert and review a project first.');const master=getMaster();if(master.inputs?.some(i=>i.name==='timeline' && i.link!=null))throw Error('Disconnect the external Timeline Builder before importing into the editable Master.');persist(master,'timeline_data',converted);master.__mmxDirectorRefresh?.();root.__status.textContent='Converted Timeline Applied · Save It As A Named Project';});}

app.registerExtension({name:'MiniMaxH3.AuthoringTools',nodeCreated(node){node.properties ||= {};syncOutputLabels(node);const type=node.comfyClass || node.type;if(type==='MiniMaxH3RefPack')assets(node);if(type==='MiniMaxH3RefModLibrary')refmods(node);if(type==='MiniMaxH3PromptForge')forge(node);if(type==='MiniMaxH3ProjectVideo')exporter(node);if(type==='MiniMaxH3ProjectImport')projectImport(node);if(['MiniMaxH3RefModLibrary','MiniMaxH3PromptForge','MiniMaxH3ProjectImport'].includes(type))fitToContent(node);if(['MiniMaxH3DirectorRefine','MiniMaxH3FrameInterpolation','MiniMaxH3ProjectVideo','MiniMaxH3PixelUpscale','MiniMaxH3PromptForge','MiniMaxH3DirectorSelfLift','MiniMaxH3DirectorSettings','MiniMaxH3LocalPromptModel'].includes(type))conditionalWidgets(node);const removed=node.onRemoved;node.onRemoved=function(...args){void cancelVision(node).catch(()=>{});return removed?.apply(this,args);};const configure=node.onConfigure;if(type==='MiniMaxH3RefPack')queueMicrotask(()=>sortPackSockets(node));node.onConfigure=function(...args){node.__mmxConfigured=true;const result=configure?.apply(this,args);syncOutputLabels(node);if(type==='MiniMaxH3RefPack')sortPackSockets(node);node.__mmxReload?.();node.__mmxUpdateVisibility?.();return result;};},setup(){const style=document.createElement('style');style.textContent=AUTHORING_CSS;style.textContent += '.lg-node-widgets:has(.mmx-ref-editor) > .lg-node-widget:not(:has(.mmx-ref-editor)){display:none!important}.mmx-ref-editor{box-sizing:border-box;padding:16px;background:#20262d;border-color:#3d4a56;font:14px/1.4 system-ui,sans-serif}.mmx-ref-editor h3{font-size:16px;margin:0 0 4px}.mmx-ref-editor .mmx-tool-status{margin:0 0 14px;color:#93a5b6;font-size:12px}.mmx-ref-editor fieldset{border:0;padding:0;margin:12px 0}.mmx-ref-editor legend{display:none}.mmx-ref-editor .mmx-tool-field{gap:16px;margin:10px 0}.mmx-ref-editor .mmx-tool-field input,.mmx-ref-editor .mmx-tool-field select{box-sizing:border-box;width:60%;max-width:60%;min-width:0;font:inherit;padding:8px 10px}.mmx-ref-editor .mmx-asset-preview{height:180px;max-width:100%;width:auto;object-fit:contain;margin:16px auto;background:#141a20;border-radius:6px}.mmx-ref-editor details{border-top:1px solid #35424e;padding:10px 0}.mmx-ref-editor summary{cursor:pointer;font-weight:600;color:#c5d2df;list-style-position:inside}.mmx-ref-editor summary:hover{color:#fff}.mmx-ref-editor button{font:inherit;background:#2d3e4b;margin:8px 4px 0 0}.mmx-ref-editor input[type=file]{font-size:12px}.mmx-people-stage{position:relative;width:fit-content;max-width:100%;margin:12px auto}.mmx-people-stage>.mmx-asset-preview{display:block;width:auto;height:auto;max-height:320px;max-width:100%;margin:0}.mmx-people-boxes{position:absolute;inset:0;width:100%;height:100%;touch-action:none;cursor:crosshair}.mmx-people-boxes rect{fill:#55b8ef22;stroke:#55b8ef;stroke-width:4;cursor:move}.mmx-people-boxes text{fill:white;font:bold 30px sans-serif;pointer-events:none;paint-order:stroke;stroke:#14202b;stroke-width:5}.mmx-people-boxes .mmx-people-handle{fill:#f8d366;stroke:#263646;cursor:nwse-resize}.mmx-person-row{display:flex;align-items:center;justify-content:space-between}.mmx-person-row label{display:flex;align-items:center;gap:8px}.mmx-person-row input{width:72px!important;padding:6px;background:#151e26;color:#edf3f8;border:1px solid #536574;border-radius:4px}.mmx-ref-editor input[type=checkbox]{width:auto!important;min-width:0}.mmx-ref-editor input[type=file]::file-selector-button{padding:5px 8px;background:#354b5d;color:#edf3f8;border:0;border-radius:4px}';style.textContent += '.mmx-reference-roles{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin:12px 0}.mmx-reference-roles>strong{grid-column:1/-1}.mmx-ref-editor .mmx-reference-roles .mmx-tool-field{padding:7px 8px;margin:0;gap:6px;border:1px solid #465966;border-radius:5px;font-size:12px}.mmx-reference-roles .mmx-tool-field:has(input:checked){background:#304b60;border-color:#6fa4c6}.mmx-role-help{font-size:12px;color:#aebfcc;margin:8px 0 12px}.mmx-forge-editor details{border-top:1px solid #3d4a56;padding:9px 0}.mmx-forge-editor summary{cursor:pointer;color:#c8d7e4}.mmx-forge-editor textarea{box-sizing:border-box;resize:vertical}.mmx-authoring-tool label[hidden]{display:none!important}';style.textContent += '.mmx-crop-stage{position:relative;width:fit-content;max-width:100%;margin:12px auto;user-select:none}.mmx-ref-editor .mmx-crop-stage>.mmx-asset-preview{display:block;width:auto;height:auto;max-height:320px;max-width:100%;margin:0;border-radius:0}.mmx-crop-layer{position:absolute;inset:0;overflow:hidden;pointer-events:none;touch-action:none}.mmx-crop-layer.mmx-crop-active{pointer-events:auto;cursor:crosshair}.mmx-crop-box{position:absolute;box-sizing:border-box;border:1px solid #fff;box-shadow:0 0 0 9999px rgba(8,12,16,.58);background-image:linear-gradient(to right,transparent calc(33.33% - .5px),#ffffff59 calc(33.33% - .5px),#ffffff59 calc(33.33% + .5px),transparent calc(33.33% + .5px),transparent calc(66.66% - .5px),#ffffff59 calc(66.66% - .5px),#ffffff59 calc(66.66% + .5px),transparent calc(66.66% + .5px)),linear-gradient(to bottom,transparent calc(33.33% - .5px),#ffffff59 calc(33.33% - .5px),#ffffff59 calc(33.33% + .5px),transparent calc(33.33% + .5px),transparent calc(66.66% - .5px),#ffffff59 calc(66.66% - .5px),#ffffff59 calc(66.66% + .5px),transparent calc(66.66% + .5px))}.mmx-crop-active .mmx-crop-box{cursor:move}.mmx-crop-full .mmx-crop-box{box-shadow:none;background-image:none;border-color:#ffffff40}.mmx-crop-full .mmx-crop-layer:not(.mmx-crop-active) .mmx-crop-box{display:none}.mmx-crop-handle{position:absolute;width:12px;height:12px;margin:-6px 0 0 -6px;background:#fff;border:1px solid #1d2730;border-radius:2px;box-sizing:border-box;display:none}.mmx-crop-active .mmx-crop-handle{display:block}.mmx-crop-handle[data-handle=nw]{left:0;top:0;cursor:nwse-resize}.mmx-crop-handle[data-handle=n]{left:50%;top:0;cursor:ns-resize}.mmx-crop-handle[data-handle=ne]{left:100%;top:0;cursor:nesw-resize}.mmx-crop-handle[data-handle=e]{left:100%;top:50%;cursor:ew-resize}.mmx-crop-handle[data-handle=se]{left:100%;top:100%;cursor:nwse-resize}.mmx-crop-handle[data-handle=s]{left:50%;top:100%;cursor:ns-resize}.mmx-crop-handle[data-handle=sw]{left:0;top:100%;cursor:nesw-resize}.mmx-crop-handle[data-handle=w]{left:0;top:50%;cursor:ew-resize}.mmx-crop-tools{display:flex;flex-wrap:wrap;align-items:center;gap:10px}.mmx-crop-tools .mmx-tool-field{flex:1 1 220px;margin:0}.mmx-crop-readout{color:#aebfcc;font-size:12px;font-variant-numeric:tabular-nums}.mmx-ref-editor .mmx-crop-tools button{margin:0}';document.head.append(style);}});

api.addEventListener?.('minimax_refine_seed',event=>{
  const data=event.detail;const node=app.graph?.getNodeById(Number(data?.node_id));
  if(!node || (node.comfyClass || node.type)!=='MiniMaxH3DirectorRefine')return;
  const seed=widget(node,'refine_seed');
  if(seed && String(seed.value)===String(data.used_seed)){seed.value=String(data.next_seed);seed.callback?.(seed.value);app.graph?.setDirtyCanvas(true,true);}
});
