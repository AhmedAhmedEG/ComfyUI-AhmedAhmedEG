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
function discardInvalidatedPreviews(info) {
  const invalidated=new Set(info.invalidated_clip_ids || []);
  if(!invalidated.size)return Promise.resolve();
  const update=revisionUpdates.then(async()=>{
    let revisions={};
    try{revisions=JSON.parse(globalThis.localStorage?.getItem(revisionStorage) || '{}');}catch{}
    for(const [url,entry] of Object.entries(revisions)){
      if(entry.project!==info.project_id || !Object.keys(entry.generations || {}).some(clip=>invalidated.has(clip)))continue;
      await evictPreview(url);delete revisions[url];
    }
    try{globalThis.localStorage?.setItem(revisionStorage,JSON.stringify(revisions));}catch{}
  });
  revisionUpdates=update.catch(()=>{});return update;
}
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

const PREVIEW_CSS=`
.mmx-smart-preview{display:flex;flex-direction:column;gap:10px;height:100%;min-height:0;box-sizing:border-box;font:13px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif;color:#e6e9ec}
.mmx-smart-preview[hidden]{display:none}
.mmx-pv-head{display:flex;flex-direction:column;gap:8px}
.mmx-pv-row{display:grid;grid-template-columns:52px minmax(0,1fr);align-items:center;gap:8px}
.mmx-pv-row[hidden]{display:none}
.mmx-pv-label{font-size:11px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:#8d98a3}
.mmx-pv-seg{display:inline-flex;flex-wrap:wrap;gap:2px;padding:3px;background:#161a1e;border:1px solid #2b333b;border-radius:9px;justify-self:start}
.mmx-pv-pill{appearance:none;border:0;background:transparent;color:#aab4be;font:inherit;font-size:12px;padding:4px 11px;border-radius:6px;cursor:pointer}
.mmx-pv-pill:hover{color:#fff;background:#232a31}
.mmx-pv-pill.active{background:#3b6fd8;color:#fff}
.mmx-pv-chips{display:flex;gap:6px;overflow-x:auto;padding:2px 0 4px;scrollbar-width:thin}
.mmx-pv-chip{appearance:none;flex:0 0 auto;display:inline-flex;align-items:center;gap:6px;max-width:190px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
 border:1px solid #2f3842;background:#1f252b;color:#cdd5dc;font:inherit;font-size:12px;padding:4px 10px;border-radius:999px;cursor:pointer}
.mmx-pv-chip:hover{border-color:#4a5866;color:#fff}
.mmx-pv-chip.active{background:#22385f;border-color:#3b6fd8;color:#fff}
.mmx-pv-chip.dim{opacity:.45}
.mmx-pv-num{display:inline-grid;place-items:center;min-width:18px;height:18px;padding:0 4px;box-sizing:border-box;border-radius:9px;background:#2b333b;color:#cdd5dc;font-size:10.5px;font-weight:600}
.mmx-pv-chip.active .mmx-pv-num{background:#3b6fd8;color:#fff}
.mmx-pv-sep{flex:0 0 1px;align-self:stretch;margin:2px 2px;background:#2f3842}
.mmx-pv-stage{position:relative;flex:1 1 auto;background:#0c0e10;border:1px solid #232a31;border-radius:10px;overflow:hidden;min-height:180px;display:grid;place-items:center}
.mmx-pv-stage video{display:block;width:100%;height:100%;max-height:100%;object-fit:contain;background:#000}
.mmx-pv-stage video[hidden]{display:none}
.mmx-preview-empty{color:#7d8893;font-size:13px;padding:40px 16px;text-align:center}
.mmx-preview-empty[hidden]{display:none}
.mmx-pv-foot{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px}
.mmx-preview-status{color:#9aa5b0;font-size:12px;min-width:0;flex:1 1 220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mmx-pv-tools{display:flex;flex-wrap:wrap;align-items:center;gap:6px}
.mmx-pv-tools select{height:28px;padding:0 8px;background:#1f252b;color:#e6e9ec;border:1px solid #2f3842;border-radius:7px;font:inherit;font-size:12px}
.mmx-pv-toggle{display:inline-flex;align-items:center;gap:5px;height:28px;padding:0 9px;border:1px solid #2f3842;border-radius:7px;background:#1f252b;color:#cdd5dc;font-size:12px;cursor:pointer;user-select:none}
.mmx-pv-toggle input{margin:0;accent-color:#3b6fd8}
.mmx-pv-btn{display:inline-flex;align-items:center;height:28px;padding:0 12px;border:1px solid #2f3842;border-radius:7px;background:#1f252b;color:#e6e9ec;font:inherit;font-size:12px;cursor:pointer;text-decoration:none}
.mmx-pv-btn:hover{border-color:#4a5866}
.mmx-pv-btn[hidden]{display:none}
.mmx-pv-primary{background:#3b6fd8;border-color:#3b6fd8;color:#fff}
.mmx-pv-primary:hover{background:#4a7ce0}
.mmx-pv-outputs{font-size:11.5px;color:#8d98a3;padding:6px 10px;border:1px dashed #2f3842;border-radius:8px}
`;
function installPreviewCss(){
  if(typeof document==='undefined' || document.getElementById('mmx-preview-css'))return;
  const style=document.createElement('style');style.id='mmx-preview-css';style.textContent=PREVIEW_CSS;document.head.append(style);
}

export function installSmartPreview({root, toolbar, timelinePanel, inspector, node, api, getTimeline, getOptions, saveOptions, standalone = false, hasMasterInput=()=>true}) {
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
  installPreviewCss();
  const header = document.createElement("div"); header.className = "mmx-pv-head";
  // The selects hold the state (and are what the node saves); the pills and chips drive them.
  const scope = document.createElement("select"); scope.className = "mmx-pv-model"; scope.hidden = true;
  scope.setAttribute("aria-label", "Preview scope");
  for (const [value, text] of [["latest", "Latest clip"], ["full", "Full video"], ["clips", "Chosen clips"]]) {
    const option = document.createElement("option"); option.value = value; option.textContent = text; scope.append(option);
  }
  const validScope=v=>['full','clips'].includes(v)?v:'latest';
  scope.value = validScope(getOptions().scope);
  let chosenClips=Array.isArray(getOptions().clip_ids)?getOptions().clip_ids.map(String):[];
  let lastInfo=null;
  const quality=document.createElement('select');quality.className='mmx-preview-quality';quality.setAttribute('aria-label','Preview Resolution');
  quality.title='Resolution of the preview and of the images output';
  for(const [value,text] of [['original','Original size'],['1080p','1080p'],['720p','720p'],['540p','540p · smaller']]){
    const option=document.createElement('option');option.value=value;option.textContent=text;quality.append(option);
  }
  quality.value=getOptions().quality || 'original';
  const label = document.createElement("span"); label.className = "mmx-preview-status"; label.textContent = "No completed clips yet.";
  const autoplayLabel = document.createElement("label"); autoplayLabel.className='mmx-pv-toggle';
  const autoplay = document.createElement("input"); autoplay.type = "checkbox"; autoplay.checked = !!getOptions().autoplay;
  autoplayLabel.append(autoplay, document.createTextNode("Autoplay"));
  const loopLabel = document.createElement("label"); loopLabel.className='mmx-pv-toggle';
  const loop = document.createElement("input"); loop.type = "checkbox"; loop.checked = !!getOptions().loop;
  loopLabel.append(loop, document.createTextNode("Loop"));
  const save = document.createElement("a"); save.textContent = "Save preview"; save.className = "mmx-pv-btn mmx-pv-primary";
  save.hidden = true; save.download = "minimax-preview.mp4";
  const refresh = document.createElement("button"); refresh.className = "mmx-pv-btn"; refresh.textContent = "Refresh";
  const stream=document.createElement('select');stream.className='mmx-pv-model';stream.hidden=true;stream.setAttribute('aria-label','Preview Stage');
  const stageName=v=>v==='final'?'Final':v==='first_pass'?'First pass':v==='pre_refine'?'Before refine':v.startsWith('pass:')?'Refine pass '+v.slice(5):v;
  const setStageOptions=values=>{
    const current=stream.value || getOptions().stream || 'final';
    const list=[...new Set(['final','first_pass','pre_refine',...values,...(current?[current]:[])])].filter(v=>/^(final|first_pass|pre_refine|pass:\d+)$/.test(v));
    stream.replaceChildren(...list.map(v=>{const o=document.createElement('option');o.value=v;o.textContent=stageName(v);return o;}));
    stream.value=list.includes(current)?current:'final';
  };
  setStageOptions([]);
  stream.value=getOptions().stream || 'final';if(!stream.value)stream.value='final';
  // Stage pills: only stages this project really has.
  const stageRow=document.createElement('div');stageRow.className='mmx-pv-row';
  const stageTitle=document.createElement('span');stageTitle.className='mmx-pv-label';stageTitle.textContent='Stage';
  const stagePills=document.createElement('div');stagePills.className='mmx-pv-seg';stagePills.setAttribute('role','radiogroup');stagePills.setAttribute('aria-label','Stage');
  stageRow.append(stageTitle,stagePills);
  // Clip chips: Latest, All, or any set of clips.
  const clipRow=document.createElement('div');clipRow.className='mmx-pv-row';
  const clipTitle=document.createElement('span');clipTitle.className='mmx-pv-label';clipTitle.textContent='Clips';
  const clipChips=document.createElement('div');clipChips.className='mmx-pv-chips';clipChips.setAttribute('aria-label','Clips to play and output');
  clipRow.append(clipTitle,clipChips);
  const outputsNote=document.createElement('div');outputsNote.className='mmx-pv-outputs';
  const footer=document.createElement('div');footer.className='mmx-pv-foot';
  const footerTools=document.createElement('div');footerTools.className='mmx-pv-tools';
  footerTools.append(quality,autoplayLabel,loopLabel,refresh,save);
  footer.append(label,footerTools);
  header.append(scope,stream,stageRow,clipRow);
  const renderStages=()=>{
    const values=[...new Set([...(lastInfo?.streams || ['final']),stream.value])];
    stageRow.hidden=values.length<2;
    stagePills.replaceChildren(...(stageRow.hidden?[]:values).map(v=>{
      const b=document.createElement('button');b.type='button';b.className='mmx-pv-pill'+(v===stream.value?' active':'');
      b.textContent=stageName(v);b.setAttribute('role','radio');b.setAttribute('aria-checked',String(v===stream.value));
      b.onclick=()=>{if(stream.value===v)return;stream.value=v;stream.onchange();};return b;}));
  };
  const timelineClips=()=>{
    const known=new Map((lastInfo?.clips || []).map(c=>[String(c.id),c]));
    return (getTimeline().clips || []).map((c,i)=>({id:String(c.id ?? `clip_${i+1}`),name:c.name || `Clip ${i+1}`,index:i,ready:known.get(String(c.id))?.ready}));
  };
  const renderClips=()=>{
    const clips=timelineClips();
    const chip=(text,active,onclick,extra={})=>{const b=document.createElement('button');b.type='button';b.className='mmx-pv-chip'+(active?' active':'')+(extra.dim?' dim':'');b.setAttribute('aria-pressed',String(!!active));b.title=extra.title || '';b.onclick=onclick;
      if(extra.num!=null){const n=document.createElement('span');n.className='mmx-pv-num';n.textContent=extra.num;b.append(n);}b.append(document.createTextNode(text));return b;};
    const setScope=value=>{if(scope.value===value)return;scope.value=value;scope.onchange();};
    const items=[chip('Latest',scope.value==='latest',()=>setScope('latest'),{title:'The most recently generated clip'}),
      chip('All',scope.value==='full',()=>setScope('full'),{title:'Every generated clip, in timeline order'})];
    const sep=document.createElement('span');sep.className='mmx-pv-sep';items.push(sep);
    for(const c of clips){
      const on=scope.value==='clips' && chosenClips.includes(c.id);
      items.push(chip(c.name,on,()=>{
        let next=scope.value==='clips'?[...chosenClips]:[];
        next=next.includes(c.id)?next.filter(id=>id!==c.id):[...next,c.id];
        chosenClips=clips.map(x=>x.id).filter(id=>next.includes(id));
        if(scope.value!=='clips')scope.value='clips';
        scope.onchange();
      },{num:c.index+1,dim:c.ready===false,title:c.ready===false?'No saved result at this stage yet':'Click to add or remove this clip'}));
    }
    clipChips.replaceChildren(...items);
    const chosenCount=scope.value==='clips'?chosenClips.length:0;
    const what=scope.value==='latest'?'the latest clip':scope.value==='full'?'all generated clips':chosenCount?`${chosenCount} chosen clip${chosenCount>1?'s':''}`:'no clips yet: pick some above';
    outputsNote.textContent=`Plays and sends to the images / audio outputs: ${what} · ${stageName(stream.value)} · ${quality.selectedOptions?.[0]?.textContent || 'Original size'}`;
  };
  const renderPicker=()=>{renderStages();renderClips();};
  const empty = document.createElement("div"); empty.className = "mmx-preview-empty";
  empty.textContent = "Your completed clip will appear here.";
  const video = document.createElement("video"); video.controls = true; video.playsInline = true; video.preload = "auto"; video.hidden = true;
  video.loop = loop.checked;
  video.setAttribute("aria-label", "Generated video preview");
  const stage=document.createElement('div');stage.className='mmx-pv-stage';stage.append(empty,video);
  panel.append(header, stage, footer, outputsNote); root.append(panel);
  renderPicker();
  let request = 0, controller, disposed = false, source = "", checking = false;
  let project = getTimeline().project_id;
  let statusText='';
  let blobUrl='', warmRevision='', loadingSource='', segmentPlayer;
  let displayedDownload,downloadController,downloadBusy=false;
  const downloadUrls=new Map();
  const setDownload=info=>{displayedDownload={path:`/minimax_director/preview/media?${new URLSearchParams({project_id:info.project_id,key:info.key,download:'1',...(info.cache_read_only?{read_only:'1'}:{})})}`,
    generations:info.clip_generations || {},
    name:`${info.project_id}-${info.scope==='full'?'full-video':info.scope==='clips'?'chosen-clips':'latest-clip'}-${info.key.slice(0,8)}.mp4`};};
  save.onclick=async event=>{
    event.preventDefault();event.stopPropagation();
    if(downloadBusy || disposed)return;
    if(!displayedDownload){label.textContent='Wait for the preview to open before saving.';return;}
    const selected={...displayedDownload};downloadBusy=true;
    downloadController=new AbortController();save.textContent='Preparing download…';save.setAttribute('aria-busy','true');
    try{
      // Use ComfyUI's authenticated fetch path, including through browser tunnels.
      // The link alone offered no progress/error feedback and could be intercepted
      // by graph/browser navigation. Capture the displayed revision before awaiting.
      const response=await api.fetchApi(selected.path,{signal:downloadController.signal});
      if(!response.ok){let message=`Download failed (HTTP ${response.status}).`;try{message=(await response.json()).error || message;}catch{}throw new Error(message);}
      const type=response.headers?.get?.('Content-Type') || '';
      if(type && !type.includes('video/mp4') && !type.includes('application/octet-stream'))throw new Error('Server returned a non-video response. Refresh the preview and retry.');
      save.textContent='Downloading…';const blob=await response.blob();
      if(disposed)return;
      if(!blob.size)throw new Error('The downloaded preview was empty.');
      const url=URL.createObjectURL(blob),link=document.createElement('a');
      link.href=url;link.download=selected.name;link.style.display='none';document.body.append(link);link.click();link.remove();
      const timer=setTimeout(()=>{URL.revokeObjectURL(url);downloadUrls.delete(url);},60000);downloadUrls.set(url,timer);
      label.textContent='Download ready · '+selected.name;
    }catch(error){if(!disposed && error.name!=='AbortError')label.textContent='Save preview failed: '+error.message;}
    finally{downloadBusy=false;if(!disposed){save.textContent='Save preview';save.removeAttribute('aria-busy');}}
  };
  let failedRevision='', retryCount=0, retryAt=0, recovering=false, eviction=Promise.resolve();
  const persist = () => {saveOptions({scope: scope.value, clip_ids: chosenClips, quality:quality.value,stream:stream.value, autoplay: autoplay.checked, loop: loop.checked, open: !panel.hidden});renderPicker();};
  let positionWritten=0,mediaReady=false;
  const savePosition = (force=false) => {
    if(!hasMasterInput())return;
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
    scope.value=validScope(options.scope);
    chosenClips=Array.isArray(options.clip_ids)?options.clip_ids.map(String):[];
    quality.value=options.quality || 'original';if(!quality.value)quality.value='original';
    setStageOptions([]);stream.value=options.stream || 'final';if(!stream.value)stream.value='final';
    renderPicker();
    autoplay.checked=!!options.autoplay;
    loop.checked=!!options.loop;video.loop=loop.checked;
    return options;
  };
  const stop = () => {
    loadingSource='';
    savePosition(true);mediaReady=false;
    segmentPlayer?.dispose();segmentPlayer=null;
    video.pause(); video.removeAttribute("src"); video.load(); source = ""; save.hidden = true;
    displayedDownload=null;
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
    renderPicker();
    const token = ++request; controller?.abort(); controller = new AbortController();
    checking = true;
    if (!source) label.textContent = "Checking completed clips…";
    try {
      const response = await api.fetchApi("/minimax_director/preview/info", {method: "POST",
        headers: {"Content-Type": "application/json"}, signal: controller.signal,
        body: JSON.stringify({timeline: getTimeline(), scope: scope.value, clip_ids: chosenClips, quality:quality.value,stream:stream.value,master_input:hasMasterInput()})});
      const info = await response.json();
      if (disposed || token !== request || panel.hidden) return;
      if (!response.ok) throw new Error(info.error || "Preview unavailable.");
      if(info.clips || info.streams){lastInfo=info;if(info.streams)setStageOptions(info.streams);}
      renderPicker();
      if(!info.cache_read_only && hasMasterInput() && info.invalidated_clip_ids?.length){
        const invalidated=new Set(info.invalidated_clip_ids);
        for(const streamName of ['final','first_pass']){
          const key=`${info.project_id}:${streamName}`,observed=observedGenerations.get(key) || new Map();
          for(const clip of invalidated)observed.set(clip,null);
          observedGenerations.set(key,observed);
        }
        await discardInvalidatedPreviews(info);
        if(disposed || token!==request || panel.hidden)return;
        if(Object.keys(displayedDownload?.generations || {}).some(clip=>invalidated.has(clip)))stop();
      }
      if (!info.found) {
        // A transient empty manifest/run response must not erase playable media.
        if(scope.value==='clips' && source && !chosenClips.length){stop();}
        label.textContent = source ? statusText+' · Waiting for an updated result…' : info.label || "No completed clips yet. Generate a shot first.";
        return;
      }
      const readOnly=!!info.cache_read_only || !hasMasterInput();
      const observationKey=`${info.project_id}:${info.stream || 'final'}`;
      const observed=observedGenerations.get(observationKey) || new Map();
      if(!readOnly){
        for(const clip of info.invalidated_clip_ids || [])observed.set(clip,null);
        for(const [clip,generation] of Object.entries(info.clip_generations || {}))observed.set(clip,generation);
        observedGenerations.set(observationKey,observed);
      }
      if(observedGenerations.size>32)observedGenerations.delete(observedGenerations.keys().next().value);
      const path = `/minimax_director/preview/media?${new URLSearchParams({project_id: info.project_id, key: info.key,...(readOnly?{read_only:'1'}:{})})}`;
      const url = api.apiURL(path);
      statusText = `${info.scope === "latest" ? "Latest clip" : info.scope === "clips" ? "Chosen" : "All clips"} · ${info.label}`;
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
            source=url;setDownload(info);loadingSource='';video.hidden=false;empty.hidden=true;
            segmentPlayer=createSegmentPlayer(video,info.playback,p=>readOnly?api.fetchApi(p,{cache:'no-store'}):openPreviewStream(api,p),error=>{
              if(disposed || source!==url)return;
              console.warn('Smart Preview fragment playback failed:',error);
              segmentPlayer?.dispose();segmentPlayer=null;
              video.src=url;video.load();label.textContent=statusText+' · Standard streaming';
            });
            label.textContent=statusText;
            if(!readOnly)void warmPlayback(info.playback,info).catch(()=>{});
          }).catch(()=>{if(!disposed && loadingSource===url){source=url;setDownload(info);loadingSource='';video.src=url;video.load();video.hidden=false;empty.hidden=true;}});
        } else void (readOnly?Promise.resolve(null):readyPreview(api,path)).then(blob=>{
          if(disposed || panel.hidden || token!==request || loadingSource!==url)return;
          savePosition(true);mediaReady=false;
          const previousBlob=blobUrl;
          source=url;setDownload(info);loadingSource='';
          // A completed local cache can use a blob. Otherwise let the native
          // player stream/range-load immediately; never wait for response.blob().
          blobUrl=blob?URL.createObjectURL(blob):'';
          video.src=blobUrl || url;video.load();save.hidden=false;
          if(previousBlob)URL.revokeObjectURL(previousBlob);
          video.hidden=false;empty.hidden=true;label.textContent=statusText;
          if(!readOnly)void rememberPreview(api,path,info);
          if(!blob && !readOnly)void bufferedPreview(api,path).catch(error=>{
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
      if(!readOnly && warmRevision!==url){
        warmRevision=url;
        void api.fetchApi('/minimax_director/preview/info',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({timeline:getTimeline(),scope:scope.value==='latest'?'full':'latest',quality:quality.value,stream:stream.value,master_input:hasMasterInput()})})
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
    const worker=async()=>{while(cursor<parts.length && !disposed && hasMasterInput() && project===info.project_id){
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
    if(hasMasterInput())eviction=evictPreview(url);
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
  loop.onchange = () => { video.loop = loop.checked; persist(); };
  // MediaSource playback can fire 'ended' even with loop set; restart explicitly.
  video.onended = () => { if (loop.checked && !panel.hidden && !disposed) { video.currentTime = 0; video.play().catch(() => {}); } };
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
      ++request;controller?.abort();checking=false;warmRevision='';
      if (project !== getTimeline().project_id) {
        stop(); project = getTimeline().project_id;restoreOptions();
      }
      refreshPreview();
    },
    dispose() { disposed = true;downloadController?.abort();for(const [url,timer] of downloadUrls){clearTimeout(timer);URL.revokeObjectURL(url);}downloadUrls.clear(); clearInterval(poll);document.removeEventListener('visibilitychange',resume);globalThis.removeEventListener?.('online',resume);globalThis.removeEventListener?.('pagehide',leaving); ++request; controller?.abort(); stop(); }
  };
}
