import {app} from "../../scripts/app.js";
import {api} from "../../scripts/api.js";
import {installSmartPreview} from "./minimax_preview.js";

function mount(node) {
  if (node.__mmxPlayer) return;
  node.size = [Math.max(640, node.size?.[0] || 0), Math.max(440, node.size?.[1] || 0)];
  const root = document.createElement("div"); root.className = "mmx-director-root mmx-preview-node";
  root.style.cssText = "height:100%;padding:12px;box-sizing:border-box;overflow:auto";
  const toolbar = document.createElement("div"); root.append(toolbar);
  for (const name of ["pointerdown", "mousedown", "wheel"]) root.addEventListener(name, event => event.stopPropagation());
  let receivedMasterInput=false;
  const connectedMaster = () => {
    const input = node.inputs?.find(value => value.name === "project_state");
    const link = app.graph?.links?.[input?.link];
    return link && app.graph.getNodeById(link.origin_id);
  };
  const getTimeline = () => {
    const master=connectedMaster();
    let projectId='';
    try {
      const text = master?.widgets?.find(value => value.name === "timeline_data")?.value;
      if (text) projectId=(typeof text === "string" ? JSON.parse(text) : text).project_id || '';
    } catch {}
    const accepted=node.properties.mmx_preview_timeline;
    if(master && accepted && (receivedMasterInput || accepted.project_id===projectId))return accepted;
    return {project_id:projectId,clips:[]};
  };
  node.properties ||= {};
  const player = installSmartPreview({root, toolbar, timelinePanel: document.createElement("div"),
    inspector: document.createElement("div"), node, api, getTimeline, standalone: true,
    hasMasterInput:()=>receivedMasterInput,
    getOptions: () => node.properties.mmx_preview || {scope: "latest", autoplay: true},
    saveOptions: options => {node.properties.mmx_preview = options;node.setDirtyCanvas?.(true,true);}});
  node.__mmxPlayer = player;
  const widget = node.addDOMWidget("smart_preview", "MMX_SMART_PREVIEW", root, {serialize: false});
  widget.computeSize = () => [640, 400];
  widget.serialize = false;
  const configured = node.onConfigure;
  node.onConfigure = function (...args) {receivedMasterInput=false;const result=configured?.apply(this,args);player.restore();return result;};
  const connection = node.onConnectionsChange;
  node.onConnectionsChange = function (...args) {receivedMasterInput=false;const result=connection?.apply(this,args);player.contextChanged();return result;};
  const previous = node.onExecuted;
  node.onExecuted = function (data) {
    previous?.apply(this, arguments);
    if (data?.mmx_project?.[0]) {
      const state=JSON.parse(data.mmx_project[0]);
      if(state?.project_id && Array.isArray(state.clips)){
        node.properties.mmx_preview_timeline=state;receivedMasterInput=true;
      }
    }
    player.refresh();
  };
  const handler = event => {
    const origin=connectedMaster();
    if(!origin || String(event.detail?.node).split(':').at(-1)!==String(origin.id))return;
    if(event.detail.phase==='timeline_ready' && event.detail.timeline?.project_id){
      node.properties.mmx_preview_timeline=event.detail.timeline;receivedMasterInput=true;player.refresh();return;
    }
    if (event.detail?.project_id !== getTimeline().project_id) return;
    if(!receivedMasterInput)return;
    if(event.detail.phase==='completed')player.completed();
    else if(['preparing','sampling','refining','decoding','first_pass_ready'].includes(event.detail.phase))player.refresh();
  };
  api.addEventListener("minimax_director/shot", handler);
  const removed = node.onRemoved;
  node.onRemoved = function (...args) {player.dispose();api.removeEventListener("minimax_director/shot", handler);return removed?.apply(this,args);};
}
app.registerExtension({name: "ComfyUI.MiniMaxH3SmartPreview", nodeCreated(node) {
  if (node.comfyClass === "MiniMaxH3SmartPreview" || node.type === "MiniMaxH3SmartPreview") mount(node);
}});
