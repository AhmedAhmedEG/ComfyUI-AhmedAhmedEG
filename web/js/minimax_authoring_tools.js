import {app} from "../../scripts/app.js";
import {api} from "../../scripts/api.js";

const widget=(node,name)=>node.widgets?.find(w=>w.name===name);
const value=(node,name,fallback="")=>widget(node,name)?.value ?? fallback;
const nodes=()=> (app.rootGraph || app.graph)?._nodes || [];
const masters=()=>nodes().filter(n=>["MiniMaxH3MasterNode","MiniMaxH3MasterDirector"].includes(n.comfyClass || n.type));
const state=node=>JSON.parse(value(node,"timeline_data","{}"));
function persist(node,name,data){const w=widget(node,name);if(!w)throw Error(`Missing ${name}`);w.value=JSON.stringify(data);w.callback?.(w.value);app.graph?.setDirtyCanvas(true,true);}
function hide(node,name){const w=widget(node,name);if(w){w.type="hidden";w.hidden=true;w.computeSize=()=>[0,-4];}}
function viewURL(filename){const parts=filename.replaceAll('\\','/').split('/');return api.apiURL('/view?'+new URLSearchParams({filename:parts.pop(),subfolder:parts.join('/'),type:'input'}));}
function conditionalWidgets(node){
  const saved=new Map();for(const w of node.widgets || [])saved.set(w,{type:w.type,computeSize:w.computeSize});
  const show=(name,visible)=>{const w=widget(node,name),old=saved.get(w);if(!w || !old)return;if(visible){w.type=old.type;w.hidden=false;w.computeSize=old.computeSize;}else hide(node,name);};
  const update=()=>{const type=node.comfyClass || node.type;
    if(type==='MiniMaxH3DirectorRefine'){
      const upscale=value(node,'mode')!=='refine',latent=value(node,'upscale_method','latent')==='latent',sampling=value(node,'mode')!=='latent_upscale',global=value(node,'backend','global')==='global';
      for(const name of ['target_width','target_height','upscale_method'])show(name,upscale);
      for(const name of ['latent_upscale_model','enable_latent_chunking','upscale_precision'])show(name,(upscale || global) && latent);
      const learned=(upscale || global) && latent && value(node,'latent_upscale_model','interpolate')!=='interpolate';show('spike_guard',learned);
      for(const name of ['guard_sensitivity','guard_strength'])show(name,learned && !!value(node,'spike_guard',false));
      for(const name of ['steps','denoise','sampler','scheduler','passes','enable_tiling'])show(name,sampling);
      for(const name of ['tile_count','tile_overlap'])show(name,sampling && !global && !!value(node,'enable_tiling',false));show('memory_budget_mb',global);
    }
    if(type==='MiniMaxH3FrameInterpolation')show('quality',value(node,'provider','Linear')==='RTX');
    if(type==='MiniMaxH3ProjectVideo'){show('clip_ids',value(node,'selection','all')==='clip_ids');show('refine_pass',value(node,'stream','final')==='refine_pass');}
    node.setDirtyCanvas?.(true,true);
  };
  for(const w of node.widgets || []){const old=w.callback;w.callback=function(...args){const result=old?.apply(this,args);update();return result;};}
  node.__mmxUpdateVisibility=update;update();
}
function element(tag,text,className){const e=document.createElement(tag);if(text)e.textContent=text;if(className)e.className=className;return e;}
function field(root,label,input){const row=element("label",label,"mmx-tool-field");row.append(input);root.append(row);return input;}
function input(root,label,type,current,change){const e=document.createElement("input");e.type=type;e.value=current ?? "";e.onchange=()=>change(e.value);return field(root,label,e);}
function choice(root,label,options,current,change){const e=document.createElement("select");for(const [v,t] of options.map(o=>Array.isArray(o)?o:[o,o])){const x=element("option",t);x.value=v;e.append(x);}e.value=current;e.onchange=()=>change(e.value);return field(root,label,e);}
function button(root,label,action){const b=element("button",label);b.onclick=async()=>{b.disabled=true;try{await action();}catch(e){const status=root.__status || root.closest('.mmx-authoring-tool')?.__status;if(status){status.textContent=e.message;status.dataset.error="true";}}finally{b.disabled=false;}};root.append(b);return b;}
async function request(path,body,signal){const r=await api.fetchApi(path,{method:body===undefined?"GET":"POST",headers:body===undefined?{}:{"Content-Type":"application/json"},body:body===undefined?undefined:JSON.stringify(body),signal});const data=await r.json();if(!r.ok)throw Error(data.error || `HTTP ${r.status}`);return data;}
function mount(node,title){if(node.__mmxTools)return node.__mmxTools;const root=element("div",null,"mmx-authoring-tool");root.append(element("h3",title));root.__status=element("p","Ready","mmx-tool-status");root.append(root.__status);for(const event of ["pointerdown","mousedown","wheel"])root.addEventListener(event,e=>e.stopPropagation());node.addDOMWidget("authoring_tools","MMX_TOOLS",root,{serialize:false}).computeSize=()=>[580,500];node.size=[Math.max(600,node.size?.[0]||0),Math.max(650,node.size?.[1]||0)];node.__mmxTools=root;return root;}
function masterPicker(root,node){const picker=field(root,"Master",document.createElement("select"));const refresh=()=>{picker.replaceChildren();for(const n of masters()){const o=element("option",`${n.title || "Master"} · ${n.id}`);o.value=n.id;picker.append(o);}picker.value=node.properties.mmx_target || picker.options[0]?.value;};refresh();picker.onchange=()=>{node.properties.mmx_target=picker.value;};button(root,"Refresh Masters",refresh);return ()=>{const master=masters().find(n=>String(n.id)===picker.value);if(!master)throw Error("Choose a Master in this workflow.");return master;};}

function forge(node){const root=mount(node,"Prompt Forge · Draft And Review");const getMaster=masterPicker(root,node);let controller=null,sequence=0,draft=null;
  const editor=field(root,"Review Draft JSON",document.createElement("textarea"));editor.rows=12;editor.placeholder="Generate a draft, review its prompts, then Apply.";
  const history=choice(root,"Draft History",[],"",index=>{draft=node.properties.mmx_draft_history?.[Number(index)];if(draft)editor.value=JSON.stringify(draft,null,2);});
  const updateHistory=()=>{history.replaceChildren();(node.properties.mmx_draft_history || []).forEach((d,i)=>{const o=element("option",`${i+1} · ${d.count} Clips`);o.value=i;history.append(o);});};updateHistory();node.__mmxReload=updateHistory;
  const key=input(root,"Session API Key","password","",()=>{});key.autocomplete="off";
  const vision=document.createElement('input');vision.type='checkbox';vision.checked=!!node.properties.mmx_vision;field(root,'Send Reference Pictures',vision);vision.onchange=()=>node.properties.mmx_vision=vision.checked;
  const policy=choice(root,"Apply Policy",["replace","append"],"replace",()=>{});
  button(root,"Create Draft",async()=>{const master=getMaster();const timeline=state(master);const epoch=++sequence;controller?.abort();controller=new AbortController();root.__status.textContent="Generating Draft…";
    const descriptions=JSON.parse(value(node,"shot_descriptions","[]"));
    const generatorInput=node.inputs?.find(i=>i.name==='generator');const link=app.graph?.links?.[generatorInput?.link];const provider=link && app.graph.getNodeById(link.origin_id);
    const result=await request('/minimax_director/forge/draft',{timeline,instruction:value(node,"instruction"),count:Number(value(node,"shot_count",1)),backend:value(node,"backend","ollama"),endpoint:value(node,"endpoint"),model:provider?value(provider,"model_name"):value(node,"model_name"),local_backend:provider?value(provider,"backend","transformers"):"transformers",device:provider?value(provider,"device","cpu"):"cpu",projection:provider?value(provider,"projection"):"",vision_ids:vision.checked?[...(timeline.references || []),...(timeline.available_refs || [])].filter(r=>r.filename && ['image','video'].includes(r.type)).slice(0,12).map(r=>r.id):[],api_key:key.value || value(node,"api_key"),creativity:Number(value(node,"creativity",4)),detail:Number(value(node,"detail",6)),shot_descriptions:descriptions},controller.signal);
    if(epoch!==sequence)return;draft=result;editor.value=JSON.stringify(result,null,2);node.properties.mmx_draft_history=[result,...(node.properties.mmx_draft_history || [])].slice(0,3);updateHistory();root.__status.textContent="Draft Ready · Review Before Applying";
  });
  button(root,"Cancel Request",()=>{sequence++;controller?.abort();root.__status.textContent="Request Cancelled · No Draft Applied";});
  button(root,"Apply Reviewed Draft",async()=>{const master=getMaster();if(master.inputs?.some(i=>i.name==='timeline' && i.link!=null))throw Error("Timeline Builder owns this Master. Apply changes to the builder's groups instead.");const reviewed=JSON.parse(editor.value);const result=await request('/minimax_director/forge/apply',{timeline:state(master),draft:reviewed,policy:policy.value});persist(master,'timeline_data',result.timeline);master.__mmxDirectorRefresh?.();root.__status.textContent="Reviewed Draft Applied";});
  button(root,"Clear Draft History",()=>{node.properties.mmx_draft_history=[];updateHistory();editor.value="";});
  const removed=node.onRemoved;node.onRemoved=function(...args){controller?.abort();sequence++;return removed?.apply(this,args);};
}

function refmods(node){hide(node,'library_data');const root=mount(node,"RefMod Library");const list=element("div");root.append(list);let rows=JSON.parse(value(node,'library_data','[]'));const save=()=>persist(node,'library_data',rows);
  const draw=async()=>{const entries=await request('/minimax_director/refmods');list.replaceChildren();for(const entry of entries){const box=element("fieldset");box.append(element("legend",entry.name));const enabled=document.createElement('input');enabled.type='checkbox';let row=rows.find(r=>r.name===entry.name);enabled.checked=!!row;field(box,'Use RefMod',enabled);enabled.onchange=()=>{if(enabled.checked){row={id:'library_'+crypto.randomUUID(),name:entry.name,description:entry.description || '',strength:1};rows.push(row);}else{rows=rows.filter(r=>r.name!==entry.name);row=null;}save();};
      input(box,'Description','text',row?.description ?? entry.description,v=>{if(!row){enabled.checked=true;row={id:'library_'+crypto.randomUUID(),name:entry.name,strength:1};rows.push(row);}row.description=v;save();});
      const strength=input(box,'Strength','number',row?.strength ?? 1,v=>{if(!row){enabled.checked=true;row={id:'library_'+crypto.randomUUID(),name:entry.name,description:entry.description || ''};rows.push(row);}row.strength=Number(v);save();});strength.min=0;strength.max=4;strength.step=.05;list.append(box);}
    root.__status.textContent=`${entries.length} Installed RefMods`;
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
      if(!['image','video','audio','filename'].includes(w.name))continue;
      const callback=w.callback;w.callback=function(...args){const result=callback?.apply(this,args);draw();return result;};
    }}
    const filename=origin.widgets?.find(w=>['image','video','audio','filename'].includes(w.name) && typeof w.value==='string')?.value;
    return filename || '';
  }
  const draw=()=>{list.replaceChildren();const slots=(node.inputs || []).filter(i=>/^(image|video|audio)_\d+$/.test(i.name) && i.link!=null).map(i=>({id:i.name,type:i.name.split('_')[0],filename:sourceFilename(i.name),settings:data.assets[i.name] ||= {}}));for(const f of data.files)slots.push({id:f.id,type:f.type,filename:f.filename,settings:f,file:true});
    if(!slots.some(a=>a.id===selected))selected=slots[0]?.id || '';
    picker.replaceChildren();for(const asset of slots){const o=element('option',`${asset.id} · ${asset.settings.name || value(node,asset.id+'_name','') || asset.filename || asset.type}`);o.value=asset.id;picker.append(o);}picker.value=selected;picker.disabled=!slots.length;node.properties.mmx_asset_selection=selected;
    for(const asset of slots.filter(a=>a.id===selected)){const a=asset.settings;const box=element('fieldset');box.append(element('legend',asset.id));list.append(box);
      const change=(key,v)=>{a[key]=v;save();};input(box,'Name','text',a.name ?? value(node,asset.id+'_name',''),v=>change('name',v));choice(box,'Role',['subject','place','style','keyframe','pose','custom'],a.role || 'subject',v=>change('role',v));input(box,'Description / Instructions','text',a.description || '',v=>change('description',v));
      let media=null;if(asset.filename){media=document.createElement(asset.type==='image'?'img':asset.type);media.src=viewURL(asset.filename);if(asset.type!=='image')media.controls=true;media.className='mmx-asset-preview';box.append(media);}
      if(asset.type==='video' && !asset.file){const slot=node.inputs?.find(i=>i.name===asset.id);const graph=node.graph || app.rootGraph || app.graph;const link=graph?.links?.[slot?.link];const origin=graph?.getNodeById(Array.isArray(link)?link[1]:link?.origin_id);const output=origin?.outputs?.[Array.isArray(link)?link[2]:link?.origin_slot || 0];if(output?.type!=='VIDEO'){const fps=input(box,'Source FPS','number',value(node,asset.id+'_fps',24),v=>{const w=widget(node,asset.id+'_fps');if(w){w.value=Number(v);w.callback?.(w.value);}});fps.min=1;fps.max=240;}}
      if(asset.type!=='image'){
        const start=input(box,'Trim Start (Seconds)','number',a.start || 0,v=>change('start',Number(v)));start.min=0;start.step=1/24;
        const end=input(box,'Trim End (Seconds, Blank = Full)','number',a.end ?? '',v=>change('end',v===''?null:Number(v)));end.min=0;end.step=1/24;
        if(asset.filename){const wave=document.createElement('canvas');wave.width=480;wave.height=60;box.append(wave);request('/minimax_director/media/waveform?'+new URLSearchParams({filename:asset.filename})).then(info=>{const c=wave.getContext('2d');c.fillStyle='#957cce';info.peaks.forEach((peak,i)=>c.fillRect(i*480/info.peaks.length,30-peak*25,2,peak*50));for(const [label,key] of [['Start','start'],['End','end']]){const handle=input(box,`${label} Handle`,'range',key==='start'?(a.start || 0):(a.end ?? info.duration),v=>{change(key,Number(v));(key==='start'?start:end).value=v;});handle.min=0;handle.max=info.duration;handle.step=1/24;}}).catch(()=>{});}
      }
      if(asset.type==='video'){
        choice(box,'Use Video As',['both','video','audio','frame'],a.media_mode || 'both',v=>change('media_mode',v));input(box,'Picked Frame (Seconds After Trim)','number',a.frame_time || 0,v=>change('frame_time',Number(v)));
        if(asset.file && media)button(box,'Add Current Frame As Image',async()=>{const result=await request('/minimax_director/media/frame',{filename:asset.filename,time:media.currentTime});data.files.push({id:'asset_'+crypto.randomUUID(),name:'Picked Frame',type:'image',filename:result.filename,scaling:'Off'});save();draw();});
      }
      if(asset.type!=='audio'){
        const adjustments=element('details');adjustments.className='mmx-asset-adjustments';adjustments.append(element('summary','Color Adjustments'));box.append(adjustments);
        a.edits ||= {};for(const [key,fallback] of [['exposure',0],['contrast',1],['saturation',1]]){const e=input(adjustments,key[0].toUpperCase()+key.slice(1),'number',a.edits[key] ?? fallback,v=>{a.edits[key]=Number(v);save();});e.step=.05;}
        const scaling=element('details');scaling.append(element('summary','Resize'));box.append(scaling);
        choice(scaling,'Scaling',['Off','Target','Fit and pad','Divisible crop'],a.scaling || 'Off',v=>{change('scaling',v);draw();});if(a.scaling && a.scaling!=='Off'){scaling.open=true;input(scaling,'Width','number',a.width || 1344,v=>change('width',Number(v)));input(scaling,'Height','number',a.height || 768,v=>change('height',Number(v)));}
        const cropping=element('details');cropping.append(element('summary','Crop'));box.append(cropping);
        const crop=a.crop || {x:0,y:0,width:1,height:1};for(const key of ['x','y','width','height']){const e=input(cropping,key[0].toUpperCase()+key.slice(1),'number',crop[key],v=>{a.crop={...crop,[key]:Number(v)};Object.assign(crop,a.crop);save();});e.min=0;e.max=1;e.step=.01;}
        if(media){const preview=element('div');preview.style.cssText='position:relative;width:fit-content;max-width:100%;margin:0 auto';media.replaceWith(preview);preview.append(media);const overlay=element('div');overlay.style.cssText=`position:absolute;pointer-events:none;border:2px solid #67c7ff;background:#67c7ff18;box-sizing:border-box;left:${crop.x*100}%;top:${crop.y*100}%;width:${crop.width*100}%;height:${crop.height*100}%`;overlay.hidden=!a.crop;preview.append(overlay);let origin=null;media.style.cursor='crosshair';media.onpointerdown=e=>{const r=media.getBoundingClientRect();origin=[Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))];media.setPointerCapture(e.pointerId);e.preventDefault();};media.onpointerup=e=>{if(!origin)return;const r=media.getBoundingClientRect();const x=Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),y=Math.max(0,Math.min(1,(e.clientY-r.top)/r.height));a.crop={x:Math.min(x,origin[0]),y:Math.min(y,origin[1]),width:Math.abs(x-origin[0]),height:Math.abs(y-origin[1])};origin=null;if(a.crop.width>.005 && a.crop.height>.005){save();draw();}else delete a.crop;};}
      }
      button(box,'Reset Asset Adjustments',()=>{if(asset.file){const identity={id:a.id,type:a.type,filename:a.filename,name:a.name};Object.keys(a).forEach(k=>delete a[k]);Object.assign(a,identity);}else data.assets[asset.id]={};save();draw();});
      if(asset.file)button(box,'Remove Asset',()=>{data.files=data.files.filter(f=>f.id!==asset.id);save();draw();});
    }root.__status.textContent=`${slots.length} References`;};
  async function upload(file){const form=new FormData();form.append('file',file,file.name);const r=await api.fetchApi('/minimax_director/media/upload',{method:'POST',body:form});const result=await r.json();if(!r.ok)throw Error(result.error || 'Upload failed');selected='asset_'+crypto.randomUUID();data.files.push({id:selected,type:result.media_type || (/\.(mp4|mov|webm|mkv)$/i.test(file.name)?'video':/\.(wav|mp3|flac|ogg)$/i.test(file.name)?'audio':'image'),name:file.name,filename:[result.subfolder,result.name].filter(Boolean).join('/'),scaling:'Off',media_mode:'both'});save();draw();}
  const files=document.createElement('input');files.type='file';files.multiple=true;files.accept='image/*,video/*,audio/*';files.onchange=async()=>{try{for(const file of files.files)await upload(file);}catch(e){root.__status.textContent=e.message;}};field(root,'Add Pack Files',files);
  root.ondragover=e=>e.preventDefault();root.ondrop=async e=>{e.preventDefault();for(const file of e.dataTransfer.files)await upload(file);};root.onpaste=async e=>{const items=[...(e.clipboardData?.files || [])];if(items.length){e.preventDefault();for(const f of items)await upload(f);}};
  node.__mmxReload=()=>{data=JSON.parse(value(node,'asset_edits','{}'));data.assets ||= {};data.files ||= [];hideNative();for(const i of node.inputs || [])if(/^video_\d+$/.test(i.name))i.type='VIDEO,IMAGE';node.widgets_start_y=undefined;const minimum=node.computeSize?.();if(minimum && node.size?.[1]>minimum[1]+160)node.setSize?.([Math.max(600,node.size[0]),minimum[1]]);draw();queueMicrotask(draw);};button(root,'Refresh References',draw);draw();const original=node.onConnectionsChange;node.onConnectionsChange=function(...args){const result=original?.apply(this,args);hideNative();draw();return result;};
}

function exporter(node){const root=mount(node,'Choose Clips To Export');const getMaster=masterPicker(root,node);const list=element('div');root.append(list);button(root,'Refresh Clips',()=>{const timeline=state(getMaster());const ids=new Set(String(value(node,'clip_ids')).split(',').filter(Boolean));list.replaceChildren();for(const clip of timeline.clips || []){const check=document.createElement('input');check.type='checkbox';check.checked=ids.has(clip.id);field(list,clip.name || clip.id,check);check.onchange=()=>{check.checked?ids.add(clip.id):ids.delete(clip.id);const w=widget(node,'clip_ids');w.value=[...ids].join(',');w.callback?.(w.value);};}root.__status.textContent='Set Selection To clip_ids To Use These Checks';});}

function projectImport(node){const root=mount(node,'Convert Upstream Project');const getMaster=masterPicker(root,node);let converted=null;const report=element('pre');root.append(report);const file=document.createElement('input');file.type='file';file.accept='.json,.zip,.ext';field(root,'Project File',file);
 button(root,'Convert And Review',async()=>{if(!file.files[0])throw Error('Choose a project file.');const form=new FormData();form.append('file',file.files[0]);const response=await api.fetchApi('/minimax_director/project/convert',{method:'POST',body:form});const result=await response.json();if(!response.ok)throw Error(result.error || 'Conversion failed');converted=result.timeline;report.textContent=JSON.stringify(result.report,null,2);const w=widget(node,'project_json');w.value=JSON.stringify(converted);widget(node,'source').value='current';root.__status.textContent='Converted · Review Warnings Before Applying';});
 button(root,'Apply Converted Timeline',()=>{if(!converted)throw Error('Convert and review a project first.');const master=getMaster();if(master.inputs?.some(i=>i.name==='timeline' && i.link!=null))throw Error('Disconnect the external Timeline Builder before importing into the editable Master.');persist(master,'timeline_data',converted);master.__mmxDirectorRefresh?.();root.__status.textContent='Converted Timeline Applied · Save It As A Named Project';});}

app.registerExtension({name:'MiniMaxH3.AuthoringTools',nodeCreated(node){node.properties ||= {};const type=node.comfyClass || node.type;if(type==='MiniMaxH3RefPack')assets(node);if(type==='MiniMaxH3RefModLibrary')refmods(node);if(type==='MiniMaxH3PromptForge')forge(node);if(type==='MiniMaxH3ProjectVideo')exporter(node);if(type==='MiniMaxH3ProjectImport')projectImport(node);if(['MiniMaxH3DirectorRefine','MiniMaxH3FrameInterpolation','MiniMaxH3ProjectVideo'].includes(type))conditionalWidgets(node);const configure=node.onConfigure;node.onConfigure=function(...args){const result=configure?.apply(this,args);node.__mmxReload?.();node.__mmxUpdateVisibility?.();return result;};},setup(){const style=document.createElement('style');style.textContent='.mmx-authoring-tool{height:100%;overflow:auto;padding:14px;background:#20272e;color:#dbe5ee;border:1px solid #506070;border-radius:8px;font:13px Arial}.mmx-authoring-tool fieldset{border:1px solid #465966;border-radius:7px;margin:12px 0;padding:12px}.mmx-tool-field{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:8px 0}.mmx-tool-field input,.mmx-tool-field select,.mmx-tool-field textarea{min-width:120px;max-width:70%;background:#151e26;color:#eee;border:1px solid #536574;border-radius:4px;padding:7px}.mmx-tool-field textarea{width:70%}.mmx-authoring-tool button{padding:8px 12px;background:#304657;color:#edf6ff;border:1px solid #607d92;border-radius:5px;margin:4px;cursor:pointer;text-align:center}.mmx-authoring-tool button:hover{background:#42617a}.mmx-authoring-tool button:disabled{opacity:.45}.mmx-asset-preview{max-width:100%;max-height:220px;display:block}.mmx-tool-status{color:#8ed5ae}.mmx-tool-status[data-error=true]{color:#ffa7a7}';style.textContent += '.lg-node-widgets:has(.mmx-ref-editor) > .lg-node-widget:not(:has(.mmx-ref-editor)){display:none!important}.mmx-ref-editor{box-sizing:border-box;padding:16px;background:#20262d;border-color:#3d4a56;font:14px/1.4 system-ui,sans-serif}.mmx-ref-editor h3{font-size:16px;margin:0 0 4px}.mmx-ref-editor .mmx-tool-status{margin:0 0 14px;color:#93a5b6;font-size:12px}.mmx-ref-editor fieldset{border:0;padding:0;margin:12px 0}.mmx-ref-editor legend{display:none}.mmx-ref-editor .mmx-tool-field{gap:16px;margin:10px 0}.mmx-ref-editor .mmx-tool-field input,.mmx-ref-editor .mmx-tool-field select{box-sizing:border-box;width:60%;max-width:60%;min-width:0;font:inherit;padding:8px 10px}.mmx-ref-editor .mmx-asset-preview{height:180px;max-width:100%;width:auto;object-fit:contain;margin:16px auto;background:#141a20;border-radius:6px}.mmx-ref-editor details{border-top:1px solid #35424e;padding:10px 0}.mmx-ref-editor summary{cursor:pointer;font-weight:600;color:#c5d2df;list-style-position:inside}.mmx-ref-editor summary:hover{color:#fff}.mmx-ref-editor button{font:inherit;background:#2d3e4b;margin:8px 4px 0 0}.mmx-ref-editor input[type=file]{font-size:12px}.mmx-ref-editor input[type=file]::file-selector-button{padding:5px 8px;background:#354b5d;color:#edf3f8;border:0;border-radius:4px}';document.head.append(style);}});
