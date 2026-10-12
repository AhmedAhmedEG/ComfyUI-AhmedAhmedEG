// On-demand player. Latest mode never requests a full-sequence media URL.
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
  const video = document.createElement("video"); video.controls = true; video.playsInline = true; video.preload = "metadata"; video.hidden = true;
  video.setAttribute("aria-label", "Generated video preview");
  panel.append(header, empty, video); root.append(panel);
  let request = 0, controller, disposed = false, source = "";
  let project = getTimeline().project_id;
  let statusText='';
  const persist = () => saveOptions({scope: scope.value, quality:quality.value,stream:stream.value,take_id:takeChoice.value, autoplay: autoplay.checked, open: !panel.hidden});
  const stop = () => {
    video.pause(); video.removeAttribute("src"); video.load(); source = ""; save.hidden = true;
    video.hidden = true; empty.hidden = false;
  };
  const refreshPreview = async () => {
    if (disposed || panel.hidden) return;
    if (!getTimeline().project_id) {stop();label.textContent = "Connect the Master's project_state output.";return;}
    const token = ++request; controller?.abort(); controller = new AbortController();
    label.textContent = "Checking completed clips…";
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
      if (!info.found) { stop(); label.textContent = "No completed clips yet. Generate a shot first."; return; }
      const url = api.apiURL(`/minimax_director/preview/media?${new URLSearchParams({project_id: info.project_id, key: info.key})}`);
      statusText = `${info.scope === "latest" ? "Latest Clip" : info.scope === 'take' ? 'Saved Take' : "Full Video"} · ${info.label}`;
      if(info.missing_clips?.length)statusText+=` · No Cached Take: ${info.missing_clips.map(c=>c.name).join(', ')}`;
      label.textContent=statusText;
      save.href = `${url}&download=1`; save.hidden = false;
      if (url !== source) {
        stop(); source = url; video.src = url; video.load(); save.hidden = false;
        video.hidden = false; empty.hidden = true;
      }
    } catch (error) {
      if (token !== request || error.name === "AbortError" || disposed) return;
      stop();label.textContent = error.message;
    }
  };
  video.onloadeddata = () => {
    if (autoplay.checked && !panel.hidden) video.play().catch(() => {});
  };
  video.onerror = () => { source='';label.textContent = "Preview could not load. Click Refresh to retry."; save.hidden = true; };
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
  stream.onchange=()=>{persist();refreshPreview();};
  quality.onchange=()=>{stop();persist();refreshPreview();};
  takeChoice.onchange=()=>{stop();persist();refreshPreview();};
  autoplay.onchange = () => { persist(); if (!autoplay.checked) video.pause(); };
  refresh.onclick = refreshPreview;
  if (standalone || getOptions().open) show(true);
  return {
    restore() {
      const options = getOptions();
      scope.value = ['full','take'].includes(options.scope) ? options.scope : "latest";
      quality.value=options.quality || 'original';
      autoplay.checked = !!options.autoplay;
      show(standalone || !!options.open);
    },
    completed() { preview.textContent = panel.hidden ? "Preview • New clip" : "Preview"; refreshPreview(); },
    refresh: refreshPreview,
    contextChanged() {
      if (project !== getTimeline().project_id) {
        project = getTimeline().project_id; ++request; controller?.abort(); stop(); refreshPreview();
      }
    },
    dispose() { disposed = true; ++request; controller?.abort(); stop(); }
  };
}
