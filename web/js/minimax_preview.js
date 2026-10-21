// Share buffered revisions between players and scope changes. Persistent browser
// storage is best effort; the bounded session cache also works in private tabs.
const previewMedia = new Map();
const pendingMedia = new Map();
const mediaStreams = new Map();
const reloadMedia = new Set();
const mediaEpochs = new Map();
const observedGenerations = new Map();
const MEDIA_LIMIT = 256 * 1024 * 1024;
let legacyCacheCleared;
const revisionStorage = 'minimax-preview-revisions-v2';
let revisionUpdates = Promise.resolve();
function rememberPreview(api, path, info) {
  // Both scopes/players can finish buffering together. Serialize the shared
  // read/evict/write so one completion cannot lose the other's revision entry.
  const update=revisionUpdates.then(()=>updatePreviewRevision(api,path,info));
  revisionUpdates=update.catch(()=>{});
  return update;
}
async function updatePreviewRevision(api, path, info) {
  const url=api.apiURL(path), generations=info.clip_generations;
  const observed=observedGenerations.get(`${info.project_id}:${info.stream || 'final'}`);
  if(observed && Object.entries(generations || {}).some(([clip,generation])=>observed.has(clip) && observed.get(clip)!==generation)){
    await evictPreview(url);return;
  }
  const invalidated=new Set(info.invalidated_clip_ids || []);
  if((!generations || !Object.keys(generations).length) && !invalidated.size)return;
  let revisions={};
  try{revisions=JSON.parse(globalThis.localStorage?.getItem(revisionStorage) || '{}');}catch{}
  for(const [old,entry] of Object.entries(revisions)) {
    if(entry.project!==info.project_id)continue;
    if(Object.keys(entry.generations || {}).some(clip=>invalidated.has(clip)) ||
      entry.stream===(info.stream || 'final') && Object.entries(generations || {}).some(([clip,generation])=>entry.generations?.[clip] && entry.generations[clip]!==generation)) {
      await evictPreview(old);delete revisions[old];
    }
  }
  delete revisions[url];revisions[url]={project:info.project_id,stream:info.stream || 'final',generations};
  try{globalThis.localStorage?.setItem(revisionStorage,JSON.stringify(Object.fromEntries(Object.entries(revisions).slice(-64))));}catch{}
}
async function bufferedPreview(api, path) {
  const url = api.apiURL(path);
  if (previewMedia.has(url)) {const blob=previewMedia.get(url);previewMedia.delete(url);previewMedia.set(url,blob);return blob;}
  if (pendingMedia.has(url)) return pendingMedia.get(url);
  const epoch=mediaEpochs.get(url) || 0;
  let streamResolve,streamReject;
  const streamReady=new Promise((resolve,reject)=>{streamResolve=resolve;streamReject=reject;});
  streamReady.catch(()=>{});mediaStreams.set(url,streamReady);
  const task=(async()=>{
    let cache, response;
    try {
      legacyCacheCleared ||= Promise.resolve(globalThis.caches?.delete?.('minimax-preview-v1'));
      await legacyCacheCleared;
      cache=await globalThis.caches?.open('minimax-preview-v2');response=reloadMedia.has(url)?null:await cache?.match(url);
    } catch {}
    if (!response) {
      response=await api.fetchApi(path,reloadMedia.has(url)?{cache:'reload'}:undefined);
      reloadMedia.delete(url);
      if (!response.ok) throw new Error('Could not buffer preview. Retry when the connection is available.');
      if(Number(response.headers?.get?.('Content-Length'))>MEDIA_LIMIT){
        await response.body?.cancel?.();
        throw Object.assign(new Error('Large preview uses browser streaming.'),{stream:true});
      }
    }
    // A stable, unread branch lets playback clone a progressive stream while
    // the same network response is being persisted. No second video download.
    streamResolve(response.clone());
    let storage=Promise.resolve();
    if(cache)storage=(async()=>{try {
        await cache.put(url,response.clone());
        const keys=await cache.keys();let bytes=0;
        for(let i=keys.length-1;i>=0;i--){const item=await cache.match(keys[i]);bytes+=Number(item.headers.get('Content-Length')) || (await item.blob()).size;if(keys.length-i>32 || bytes>1024*1024*1024)await cache.delete(keys[i]);}
      } catch {}})();
    const blob=await response.blob();
    await storage;
    if((mediaEpochs.get(url) || 0)!==epoch){await cache?.delete(url);return blob;}
    if(blob.size<=MEDIA_LIMIT){previewMedia.set(url,blob);let bytes=[...previewMedia.values()].reduce((n,b)=>n+b.size,0);while(previewMedia.size>8 || bytes>MEDIA_LIMIT){const key=previewMedia.keys().next().value;bytes-=previewMedia.get(key).size;previewMedia.delete(key);}}
    return blob;
  })();
  pendingMedia.set(url,task);
  try{return await task;}catch(error){streamReject(error);throw error;}finally{pendingMedia.delete(url);mediaStreams.delete(url);}
}

async function openPreviewStream(api,path) {
  const url=api.apiURL(path);
  if(previewMedia.has(url))return new Response(previewMedia.get(url));
  void bufferedPreview(api,path).catch(()=>{});
  const response=await mediaStreams.get(url);
  if(!response)return new Response(await bufferedPreview(api,path));
  return response.clone();
}

async function readyPreview(api, path) {
  const url=api.apiURL(path);
  if(reloadMedia.has(url))return null;
  if(previewMedia.has(url))return previewMedia.get(url);
  try {
    const response=await (await globalThis.caches?.open('minimax-preview-v2'))?.match(url);
    if(response && Number(response.headers?.get?.('Content-Length'))<=MEDIA_LIMIT){
      const blob=await response.blob();
      if(blob.size<=MEDIA_LIMIT)return blob;
    }
  } catch {}
  return null;
}

async function evictPreview(url) {
  mediaEpochs.set(url,(mediaEpochs.get(url) || 0)+1);
  if(mediaEpochs.size>256)for(const key of mediaEpochs.keys()){if(!pendingMedia.has(key)){mediaEpochs.delete(key);break;}}
  previewMedia.delete(url);
  reloadMedia.add(url);
  if(reloadMedia.size>32)reloadMedia.delete(reloadMedia.values().next().value);
  try {const cache=await globalThis.caches?.open('minimax-preview-v2');await cache?.delete(url);} catch {}
}

export function installSmartPreview({root, toolbar, timelinePanel, inspector, node, api, getTimeline, getOptions, saveOptions, standalone = false}) {
  const nodeOptions=getOptions, writeNodeOptions=saveOptions;
  const storageKey=kind=>getTimeline().project_id ? `minimax-preview-${kind}-v1:${getTimeline().project_id}:${node.id ?? 'player'}` : null;
  const readStored=kind=>{try{const value=JSON.parse(globalThis.localStorage?.getItem(storageKey(kind)) || '{}');return value && typeof value==='object' && !Array.isArray(value)?value:{};}catch{return {};}};
  getOptions=()=>{
    const nodeValue=nodeOptions() || {}, stored=readStored('options');
    return Number(stored.updated_at || 0)>Number(nodeValue.updated_at || 0)?{...nodeValue,...stored}:nodeValue;
  };
  saveOptions=value=>{
    const stored=readStored('options');
    const options={...value,updated_at:Math.max(Date.now(),Number(nodeOptions()?.updated_at || 0)+1,Number(stored.updated_at || 0)+1)};
    delete options.take_id;
    try{const key=storageKey('options');if(key)globalThis.localStorage?.setItem(key,JSON.stringify(options));}catch{}
    writeNodeOptions(options);
  };
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
  for (const [value, text] of [["latest", "Latest clip"], ["full", "Full video"]]) {
    const option = document.createElement("option"); option.value = value; option.textContent = text; scope.append(option);
  }
  scope.value = getOptions().scope === 'full' ? getOptions().scope : "latest";
  const quality=document.createElement('select');quality.className='mmx-preview-quality';quality.setAttribute('aria-label','Preview Resolution');
  for(const [value,text] of [['original','Original Resolution'],['1080p','1080p'],['720p','720p'],['540p','540p · Smaller Download']]){
    const option=document.createElement('option');option.value=value;option.textContent=text;quality.append(option);
  }
  quality.value=getOptions().quality || 'original';
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
  header.append(scope, quality, stream, label, autoplayLabel, refresh, save);
  const empty = document.createElement("div"); empty.className = "mmx-preview-empty";
  empty.textContent = "Your completed clip will appear here.";
  const video = document.createElement("video"); video.controls = true; video.playsInline = true; video.preload = "auto"; video.hidden = true;
  video.setAttribute("aria-label", "Generated video preview");
  panel.append(header, empty, video); root.append(panel);
  let request = 0, controller, disposed = false, source = "", checking = false;
  let project = getTimeline().project_id;
  let statusText='';
  let blobUrl='', warmRevision='', loadingSource='', segmentPlayer;
  let failedRevision='', retryCount=0, retryAt=0, recovering=false, eviction=Promise.resolve();
  const persist = () => saveOptions({scope: scope.value, quality:quality.value,stream:stream.value, autoplay: autoplay.checked, open: !panel.hidden});
  let positionWritten=0,mediaReady=false;
  const savePosition = (force=false) => {
    if(!mediaReady || !source || !Number.isFinite(video.currentTime) || !force && Date.now()-positionWritten<2000)return;
    positionWritten=Date.now();
    try{
      const positions=readStored('positions');delete positions[source];positions[source]=video.currentTime;
      const entries=Object.entries(positions).slice(-8),key=storageKey('positions');
      if(key)globalThis.localStorage?.setItem(key,JSON.stringify(Object.fromEntries(entries)));
    }catch{}
  };
  const restoreOptions = () => {
    const options=getOptions();
    scope.value=options.scope === 'full'?options.scope:'latest';
    quality.value=options.quality || 'original';if(!quality.value)quality.value='original';
    stream.value=options.stream || 'final';if(!stream.value)stream.value='final';
    autoplay.checked=!!options.autoplay;
    return options;
  };
  const stop = () => {
    loadingSource='';
    savePosition(true);mediaReady=false;
    segmentPlayer?.dispose();segmentPlayer=null;
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
    if(project!==getTimeline().project_id){stop();project=getTimeline().project_id;restoreOptions();}
    const token = ++request; controller?.abort(); controller = new AbortController();
    checking = true;
    if (!source) label.textContent = "Checking completed clips…";
    try {
      const response = await api.fetchApi("/minimax_director/preview/info", {method: "POST",
        headers: {"Content-Type": "application/json"}, signal: controller.signal,
        body: JSON.stringify({timeline: getTimeline(), scope: scope.value, quality:quality.value,stream:stream.value})});
      const info = await response.json();
      if (disposed || token !== request || panel.hidden) return;
      if (!response.ok) throw new Error(info.error || "Preview unavailable.");
      if (!info.found) {
        // A transient empty manifest/run response must not erase playable media.
        label.textContent = source ? statusText+' · Waiting for an updated result…' : info.label || "No completed clips yet. Generate a shot first.";
        return;
      }
      const observationKey=`${info.project_id}:${info.stream || 'final'}`;
      const observed=observedGenerations.get(observationKey) || new Map();
      for(const clip of info.invalidated_clip_ids || [])observed.set(clip,null);
      for(const [clip,generation] of Object.entries(info.clip_generations || {}))observed.set(clip,generation);
      observedGenerations.set(observationKey,observed);
      if(observedGenerations.size>32)observedGenerations.delete(observedGenerations.keys().next().value);
      const path = `/minimax_director/preview/media?${new URLSearchParams({project_id: info.project_id, key: info.key})}`;
      const url = api.apiURL(path);
      statusText = `${info.scope === "latest" ? "Latest Clip" : "Full Video"} · ${info.label}`;
      if(info.run_active)statusText+=' · Generation running';
      if(info.missing_clips?.length)statusText+=` · No Saved Result: ${info.missing_clips.map(c=>c.name).join(', ')}`;
      label.textContent=statusText+(video.hidden && source===url?' · Buffering…':'');
      save.href = `${url}&download=1`; save.hidden = false;
      if (url !== source) {
        if (failedRevision !== url) {failedRevision=url;retryCount=0;}
        recovering=false; loadingSource=url;label.textContent=statusText+' · Opening preview…';
        const supported=info.playback && globalThis.MediaSource && MediaSource.isTypeSupported(info.playback.video_mime) && MediaSource.isTypeSupported(info.playback.audio_mime);
        if(supported){
          void import('./minimax_segment_player.js').then(({createSegmentPlayer})=>{
            if(disposed || panel.hidden || token!==request || loadingSource!==url)return;
            savePosition(true);mediaReady=false;segmentPlayer?.dispose();
            if(blobUrl)URL.revokeObjectURL(blobUrl);blobUrl='';
            source=url;loadingSource='';video.hidden=false;empty.hidden=true;
            segmentPlayer=createSegmentPlayer(video,info.playback,p=>openPreviewStream(api,p),error=>{
              if(disposed || source!==url)return;
              console.warn('Smart Preview fragment playback failed:',error);
              segmentPlayer?.dispose();segmentPlayer=null;
              video.src=url;video.load();label.textContent=statusText+' · Standard streaming';
            });
            label.textContent=statusText;
            void warmPlayback(info.playback,info).catch(()=>{});
          }).catch(()=>{if(!disposed && loadingSource===url){source=url;loadingSource='';video.src=url;video.load();video.hidden=false;empty.hidden=true;}});
        } else void readyPreview(api,path).then(blob=>{
          if(disposed || panel.hidden || token!==request || loadingSource!==url)return;
          savePosition(true);mediaReady=false;
          const previousBlob=blobUrl;
          source=url;loadingSource='';
          // A completed local cache can use a blob. Otherwise let the native
          // player stream/range-load immediately; never wait for response.blob().
          blobUrl=blob?URL.createObjectURL(blob):'';
          video.src=blobUrl || url;video.load();save.hidden=false;
          if(previousBlob)URL.revokeObjectURL(previousBlob);
          video.hidden=false;empty.hidden=true;label.textContent=statusText;
          void rememberPreview(api,path,info);
          if(!blob)void bufferedPreview(api,path).catch(error=>{
            // Persistent caching is independent of playback. Do not clear a
            // playable stream or reload it when the background transfer finishes.
            if(!disposed && source===url && !error.stream)label.textContent=statusText+' · Streaming; background cache will retry on reopen.';
          });
        }).catch(error=>{if(!disposed && token===request && loadingSource===url){
          loadingSource='';
          if(source){label.textContent=statusText+' · Could not open replacement; keeping saved result. Retrying…';}
          else {retryMedia(url, error.message);}
        }});
      }
      // Prebuffer both scopes after each completion, including during a run.
      // Revision URLs deduplicate transfers; autoplay never gates buffering.
      if(warmRevision!==url){
        warmRevision=url;
        void api.fetchApi('/minimax_director/preview/info',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({timeline:getTimeline(),scope:scope.value==='latest'?'full':'latest',quality:quality.value,stream:stream.value})})
          .then(r=>r.ok?r.json():null).then(async other=>{if(other?.found && !disposed && project===other.project_id){if(other.playback && globalThis.MediaSource)return warmPlayback(other.playback,other);const path=`/minimax_director/preview/media?${new URLSearchParams({project_id:other.project_id,key:other.key})}`;await bufferedPreview(api,path);if(!disposed && warmRevision===url)await rememberPreview(api,path,other);}})
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
  const warmPlayback=async(playback,info)=>{
    const parts=[playback.audio,...playback.videos];
    // Two bounded transfers avoid launching an encoder for every clip at once.
    let cursor=0;
    const worker=async()=>{while(cursor<parts.length && !disposed && project===info.project_id){
      const part=parts[cursor++],observed=observedGenerations.get(`${info.project_id}:${info.stream || 'final'}`);
      if(Object.entries(part.generations || {}).some(([clip,generation])=>observed?.has(clip) && observed.get(clip)!==generation))continue;
      await rememberPreview(api,part.path,{...info,clip_generations:part.generations});
      await bufferedPreview(api,part.path);
    }};
    await Promise.all([worker(),worker()]);
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
  video.ontimeupdate=()=>savePosition();
  video.onpause=()=>savePosition(true);
  video.onloadedmetadata = () => {
    mediaReady=true;
    const position=Number(readStored('positions')[source]);
    if(position>0 && Number.isFinite(video.duration))video.currentTime=Math.min(position,Math.max(0,video.duration-.05));
    label.textContent=`${statusText} · ${video.videoWidth}×${video.videoHeight}`;node.setDirtyCanvas?.(true, true);};
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
  autoplay.onchange = () => { persist(); if (!autoplay.checked) video.pause(); };
  refresh.onclick = () => {retryCount=0;retryAt=0;refreshPreview();};
  // Completion websocket messages can be missed. Poll current saved results;
  // stable revision URLs avoid rebuffering unchanged results.
  const poll = setInterval(() => {void refreshPreview(true);}, 2000);
  const resume=()=>{if(document.hidden)savePosition(true);else if(!disposed && !panel.hidden)void refreshPreview(true);};
  const leaving=()=>savePosition(true);
  document.addEventListener('visibilitychange',resume);
  globalThis.addEventListener?.('online',resume);
  globalThis.addEventListener?.('pagehide',leaving);
  if (standalone || getOptions().open) show(true);
  return {
    restore() {
      const options = restoreOptions();
      show(standalone || !!options.open);
    },
    completed() { preview.textContent = panel.hidden ? "Preview • New clip" : "Preview"; refreshPreview(); },
    refresh: () => refreshPreview(),
    contextChanged() {
      if (project !== getTimeline().project_id) {
        stop(); project = getTimeline().project_id; ++request; controller?.abort(); restoreOptions(); refreshPreview();
      }
    },
    dispose() { disposed = true; clearInterval(poll);document.removeEventListener('visibilitychange',resume);globalThis.removeEventListener?.('online',resume);globalThis.removeEventListener?.('pagehide',leaving); ++request; controller?.abort(); stop(); }
  };
}
