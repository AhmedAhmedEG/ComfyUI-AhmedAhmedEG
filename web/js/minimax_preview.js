// Share buffered revisions between players and scope changes. Persistent browser
// storage is best effort; the bounded session cache also works in private tabs.
const previewMedia = new Map();
const pendingMedia = new Map();
const reloadMedia = new Set();
const MEDIA_LIMIT = 256 * 1024 * 1024;
async function bufferedPreview(api, path) {
  const url = api.apiURL(path);
  if (previewMedia.has(url)) {const blob=previewMedia.get(url);previewMedia.delete(url);previewMedia.set(url,blob);return blob;}
  if (pendingMedia.has(url)) return pendingMedia.get(url);
  const task=(async()=>{
    let cache, response;
    try {cache=await globalThis.caches?.open('minimax-preview-v1');response=reloadMedia.has(url)?null:await cache?.match(url);} catch {}
    if (!response) {
      response=await api.fetchApi(path,reloadMedia.has(url)?{cache:'reload'}:undefined);
      reloadMedia.delete(url);
      if (!response.ok) throw new Error('Could not buffer preview. Retry when the connection is available.');
      if(Number(response.headers?.get?.('Content-Length'))>MEDIA_LIMIT){
        await response.body?.cancel?.();
        throw Object.assign(new Error('Large preview uses browser streaming.'),{stream:true});
      }
      if(cache)try {
        await cache.put(url,response.clone());
        const keys=await cache.keys();let bytes=0;
        for(let i=keys.length-1;i>=0;i--){const item=await cache.match(keys[i]);bytes+=Number(item.headers.get('Content-Length')) || (await item.blob()).size;if(keys.length-i>32 || bytes>1024*1024*1024)await cache.delete(keys[i]);}
      } catch {}
    }
    const blob=await response.blob();
    if(blob.size<=MEDIA_LIMIT){previewMedia.set(url,blob);let bytes=[...previewMedia.values()].reduce((n,b)=>n+b.size,0);while(previewMedia.size>8 || bytes>MEDIA_LIMIT){const key=previewMedia.keys().next().value;bytes-=previewMedia.get(key).size;previewMedia.delete(key);}}
    return blob;
  })();
  pendingMedia.set(url,task);
  try{return await task;}finally{pendingMedia.delete(url);}
}

async function evictPreview(url) {
  previewMedia.delete(url);
  reloadMedia.add(url);
  if(reloadMedia.size>32)reloadMedia.delete(reloadMedia.values().next().value);
  try {const cache=await globalThis.caches?.open('minimax-preview-v1');await cache?.delete(url);} catch {}
}

export function installSmartPreview({root, toolbar, timelinePanel, inspector, node, api, getTimeline, getOptions, saveOptions, standalone = false}) {
  const tabs = document.createElement("div");
  tabs.className = "mmx-pill-group";
  const edit = document.createElement("button"), preview = document.createElement("button");
  edit.className = "mmx-pill-btn active"; edit.textContent = "Shots";
  preview.className = "mmx-pill-btn"; preview.textContent = "Preview";
  if (!standalone) { tabs.append(edit, preview); toolbar.prepend(tabs); }
  const panel = document.createElement("section");
  panel.className = "mmx-smart-preview"; panel.hidden = true;
  const header = document.createElement("div"); header.className = "mmx-toolbar";header.style.cssText='display:flex;flex-wrap:wrap;align-items:center;gap:8px';
  const scope = document.createElement("select"); scope.className = "mmx-language-select"; scope.style.width = "auto";
  scope.setAttribute("aria-label", "Preview scope");
  for (const [value, text] of [["latest", "Latest clip"], ["full", "Full video"], ["take", "Saved Take"]]) {
    const option = document.createElement("option"); option.value = value; option.textContent = text; scope.append(option);
  }
  scope.value = ['full','take'].includes(getOptions().scope) ? getOptions().scope : "latest";
  const quality=document.createElement('select');quality.className='mmx-preview-quality';quality.setAttribute('aria-label','Preview Resolution');
  for(const [value,text] of [['original','Original Resolution'],['1080p','1080p'],['720p','720p'],['540p','540p · Smaller Download']]){
    const option=document.createElement('option');option.value=value;option.textContent=text;quality.append(option);
  }
  quality.value=getOptions().quality || 'original';
  const takeChoice=document.createElement('select');takeChoice.className='mmx-preview-take';takeChoice.setAttribute('aria-label','Saved Take');takeChoice.hidden=true;
  const label = document.createElement("span"); label.className = "mmx-preview-status"; label.textContent = "No completed clips yet.";
  const autoplayLabel = document.createElement("label");
  const autoplay = document.createElement("input"); autoplay.type = "checkbox"; autoplay.checked = !!getOptions().autoplay;
  autoplayLabel.append(autoplay, document.createTextNode(" Autoplay"));
  const save = document.createElement("a"); save.textContent = "Save preview"; save.className = "mmx-action-btn";
  save.hidden = true; save.download = "minimax-preview.mp4";
  const refresh = document.createElement("button"); refresh.className = "mmx-action-btn"; refresh.textContent = "Refresh";
  const stream=document.createElement('select');stream.setAttribute('aria-label','Preview Stage');
  for(const [v,t] of [['final','Final Output'],['first_pass','First Pass · Review'],['pre_refine','Before Refinement'],...Array.from({length:20},(_,i)=>['pass:'+(i+1),'Refine Pass '+(i+1)])]){const o=document.createElement('option');o.value=v;o.textContent=t;stream.append(o);}
  stream.value=getOptions().stream || 'final';
  header.append(scope, quality, stream,takeChoice, label, autoplayLabel, refresh, save);
  const empty = document.createElement("div"); empty.className = "mmx-preview-empty";
  empty.textContent = "Your completed clip will appear here.";
  const video = document.createElement("video"); video.controls = true; video.playsInline = true; video.preload = "auto"; video.hidden = true;
  video.setAttribute("aria-label", "Generated video preview");
  panel.append(header, empty, video); root.append(panel);
  let request = 0, controller, disposed = false, source = "", checking = false;
  let project = getTimeline().project_id;
  let statusText='';
  let blobUrl='', warmRevision='';
  let failedRevision='', retryCount=0, retryAt=0, recovering=false, eviction=Promise.resolve();
  const persist = () => saveOptions({scope: scope.value, quality:quality.value,stream:stream.value,take_id:takeChoice.value, autoplay: autoplay.checked, open: !panel.hidden});
  const stop = () => {
    video.pause(); video.removeAttribute("src"); video.load(); source = ""; save.hidden = true;
    if(blobUrl){URL.revokeObjectURL(blobUrl);blobUrl='';}
    video.hidden = true; empty.hidden = false;
  };
  const refreshPreview = async (background = false) => {
    if (disposed || panel.hidden) return;
    if (background && (checking || recovering && (retryCount > 3 || Date.now() < retryAt))) return;
    await eviction;
    if (disposed || panel.hidden) return;
    if (!getTimeline().project_id) {stop();label.textContent = "Connect the Master's project_state output.";return;}
    const token = ++request; controller?.abort(); controller = new AbortController();
    checking = true;
    if (!source) label.textContent = "Checking completed clips…";
    try {
      takeChoice.hidden=scope.value!=='take';
      if(scope.value==='take'){
        const takesResponse=await api.fetchApi(`/minimax_director/project/takes?project_id=${encodeURIComponent(getTimeline().project_id)}`,{signal:controller.signal});
        const takes=await takesResponse.json();
        if(disposed || token!==request || panel.hidden)return;
        if(!takesResponse.ok)throw new Error(takes.error || 'Could not list saved takes.');
        const previous=takeChoice.value || getOptions().take_id;takeChoice.replaceChildren();
        for(const take of takes.filter(t=>t.has_frames)){
          const option=document.createElement('option');option.value=take.take_id;
          const name=getTimeline().clips?.find(c=>c.id===take.clip_id)?.name || take.clip_id;
          option.textContent=`${name} · ${take.width && take.height?`${take.width}×${take.height} · `:''}${new Date(take.updated_at*1000).toLocaleString()}`;
          takeChoice.append(option);
        }
        if([...takeChoice.options].some(option=>option.value===previous))takeChoice.value=previous;
        if(!takeChoice.value){stop();label.textContent='No Saved Takes Available.';return;}
        persist();
      }
      const response = await api.fetchApi("/minimax_director/preview/info", {method: "POST",
        headers: {"Content-Type": "application/json"}, signal: controller.signal,
        body: JSON.stringify({timeline: getTimeline(), scope: scope.value, quality:quality.value,stream:stream.value,take_id:scope.value==='take'?takeChoice.value:undefined})});
      const info = await response.json();
      if (disposed || token !== request || panel.hidden) return;
      if (!response.ok) throw new Error(info.error || "Preview unavailable.");
      if (!info.found) { stop(); label.textContent = info.label || "No completed clips yet. Generate a shot first."; return; }
      const path = `/minimax_director/preview/media?${new URLSearchParams({project_id: info.project_id, key: info.key})}`;
      const url = api.apiURL(path);
      statusText = `${info.scope === "latest" ? "Latest Clip" : info.scope === 'take' ? 'Saved Take' : "Full Video"} · ${info.label}`;
      if(info.run_active)statusText+=' · This Run';
      if(info.missing_clips?.length)statusText+=` · ${info.run_active?'Not Ready In This Run':'No Cached Take'}: ${info.missing_clips.map(c=>c.name).join(', ')}`;
      label.textContent=statusText+(video.hidden && source===url?' · Buffering…':'');
      save.href = `${url}&download=1`; save.hidden = false;
      if (url !== source) {
        stop();
        if (failedRevision !== url) {failedRevision=url;retryCount=0;}
        recovering=false; source = url;label.textContent=statusText+' · Buffering…';
        void bufferedPreview(api,path).then(blob=>{
          if(disposed || panel.hidden || source!==url)return;
          blobUrl=URL.createObjectURL(blob);video.src=blobUrl;video.load();save.hidden=false;
          video.hidden=false;empty.hidden=true;label.textContent=statusText;
        }).catch(error=>{if(!disposed && source===url){
          if(error.stream){video.src=url;video.load();video.hidden=false;empty.hidden=true;label.textContent=statusText;save.hidden=false;}
          else {retryMedia(url, error.message);}
        }});
      }
      // Once generation is idle, prepare the full movie without playing it.
      // This is keyed by the latest revision, so polling does not redownload it.
      if(scope.value==='latest' && !info.run_active && warmRevision!==url){
        warmRevision=url;
        void api.fetchApi('/minimax_director/preview/info',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({timeline:getTimeline(),scope:'full',quality:quality.value,stream:stream.value})})
          .then(r=>r.ok?r.json():null).then(full=>{if(full?.found && !disposed && project===full.project_id)return bufferedPreview(api,`/minimax_director/preview/media?${new URLSearchParams({project_id:full.project_id,key:full.key})}`);})
          .catch(error=>{if(!error.stream && warmRevision===url)warmRevision='';});
      }
    } catch (error) {
      if (token !== request || error.name === "AbortError" || disposed) return;
      // A background timeout is not evidence that a completed take vanished.
      // Keep its buffered pixels and let the next poll recover the connection.
      label.textContent = source ? statusText+' · Connection interrupted; retrying…' : error.message;
    } finally {
      if (token === request) checking = false;
    }
  };
  const retryMedia = (url, message) => {
    if (!url || disposed) return;
    if (failedRevision !== url) {failedRevision=url;retryCount=0;}
    retryCount++; recovering=true; retryAt=Date.now()+2000*Math.pow(2,retryCount-1);
    eviction=evictPreview(url);
    stop();
    label.textContent=retryCount<=3 ? message+' Retrying…' : message+' Use Refresh to try again.';
  };
  video.onloadeddata = () => {
    retryCount=0;recovering=false;
    if (autoplay.checked && !panel.hidden) video.play().catch(() => {});
  };
  video.onerror = () => retryMedia(source, "Preview could not load.");
  video.onloadedmetadata = () => {label.textContent=`${statusText} · ${video.videoWidth}×${video.videoHeight}`;node.setDirtyCanvas?.(true, true);};
  const show = async open => {
    panel.hidden = !open; timelinePanel.hidden = open; inspector.hidden = open;
    edit.classList.toggle("active", !open); preview.classList.toggle("active", open);
    if (open) { preview.textContent = "Preview"; await refreshPreview(); }
    else { ++request; controller?.abort(); stop(); }
    persist();
  };
  edit.onclick = () => show(false); preview.onclick = () => show(true);
  scope.onchange = () => { stop(); persist(); refreshPreview(); };
  stream.onchange=()=>{stop();persist();refreshPreview();};
  quality.onchange=()=>{stop();persist();refreshPreview();};
  takeChoice.onchange=()=>{stop();persist();refreshPreview();};
  autoplay.onchange = () => { persist(); if (!autoplay.checked) video.pause(); };
  refresh.onclick = () => {retryCount=0;retryAt=0;refreshPreview();};
  // Completion websocket messages can be missed. The server owns run-aware
  // eligibility, and stable revision URLs avoid rebuffering unchanged results.
  const poll = setInterval(() => {if(scope.value!=='take' || recovering)void refreshPreview(true);}, 2000);
  const resume=()=>{if(!document.hidden && !disposed && !panel.hidden){void refreshPreview(true);}};
  document.addEventListener('visibilitychange',resume);
  globalThis.addEventListener?.('online',resume);
  if (standalone || getOptions().open) show(true);
  return {
    restore() {
      const options = getOptions();
      scope.value = ['full','take'].includes(options.scope) ? options.scope : "latest";
      quality.value=options.quality || 'original';
      if (!quality.value) quality.value='original';
      stream.value=options.stream || 'final';
      if (!stream.value) stream.value='final';
      takeChoice.replaceChildren();
      if(options.take_id){const option=document.createElement('option');option.value=options.take_id;option.textContent='Loading saved take…';takeChoice.append(option);takeChoice.value=options.take_id;}
      autoplay.checked = !!options.autoplay;
      show(standalone || !!options.open);
    },
    completed() { preview.textContent = panel.hidden ? "Preview • New clip" : "Preview"; refreshPreview(); },
    refresh: () => refreshPreview(),
    contextChanged() {
      if (project !== getTimeline().project_id) {
        project = getTimeline().project_id; ++request; controller?.abort(); stop(); refreshPreview();
      }
    },
    dispose() { disposed = true; clearInterval(poll);document.removeEventListener('visibilitychange',resume);globalThis.removeEventListener?.('online',resume); ++request; controller?.abort(); stop(); }
  };
}
