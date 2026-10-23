import {app} from "../../scripts/app.js";
import {api} from "../../scripts/api.js";

const KEY='minimax-hardware-monitor-v1';
const SETTING='MiniMaxH3.Monitor.Visible';
const css=`
.mmx-hardware{position:fixed;z-index:1200;width:264px;max-width:calc(100vw - 16px);color:#e9edf5;background:rgba(25,30,39,.97);border:1px solid #485366;border-radius:12px;box-shadow:0 8px 30px #0005;font:12px system-ui,sans-serif;overflow:hidden;box-sizing:border-box;}
.mmx-hardware *{box-sizing:border-box}.mmx-hardware[hidden],.mmx-hardware [hidden]{display:none!important}
.mmx-hardware header{display:flex;align-items:center;gap:6px;padding:8px 10px;border-bottom:1px solid #ffffff12}
.mmx-hardware button{color:inherit;background:transparent;border:0;border-radius:5px;font:inherit;cursor:pointer;padding:4px 6px;min-height:26px}
.mmx-hardware button:hover{background:#ffffff12}.mmx-hardware button:focus-visible,.mmx-hardware select:focus-visible{outline:2px solid #8fc7ff;outline-offset:-1px}
.mmx-hardware .mmx-hardware-drag{flex:1;text-align:left;font-weight:650;cursor:grab;touch-action:none;user-select:none}.mmx-hardware-drag:active{cursor:grabbing}
.mmx-hardware-body{padding:11px 14px 12px}.mmx-hardware-device{display:block;width:100%;color:#aab9ce;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:11px;margin-bottom:12px}
.mmx-hardware select{width:100%;background:#252e3b;color:#dbe5f4;border:1px solid #485366;border-radius:5px;margin-bottom:10px;padding:4px;font:inherit}
.mmx-hardware-row{margin:10px 0}.mmx-hardware-label{display:flex;align-items:baseline;justify-content:space-between;gap:8px;margin-bottom:5px}.mmx-hardware-value{font-variant-numeric:tabular-nums;color:#dbe7fa;font-weight:600;font-size:12px}
.mmx-hardware-track{height:4px;background:#ffffff12;border-radius:8px;overflow:hidden}.mmx-hardware-fill{height:100%;width:0;background:var(--meter-color,#88baff);border-radius:inherit;transition:width .3s}
.mmx-hardware footer{color:#9baabd;display:flex;align-items:center;gap:6px;font-size:10px;margin-top:13px}.mmx-hardware-dot{width:6px;height:6px;border-radius:50%;background:#94a3b8}.mmx-hardware[data-state="live"] .mmx-hardware-dot{background:#79d5ad}.mmx-hardware[data-state="offline"] .mmx-hardware-dot{background:#e8ad78}.mmx-hardware[data-state="offline"] .mmx-hardware-track{opacity:.4}
.mmx-hardware[data-minimized="true"]{width:max-content}.mmx-hardware[data-minimized="true"] header{border-bottom:0;padding:4px 6px}.mmx-hardware[data-minimized="true"] .mmx-hardware-drag{white-space:nowrap}
@media(prefers-reduced-motion:reduce){.mmx-hardware-fill{transition:none}}
`;

export function createHardwareMonitor(client, options={}) {
    let saved={};try{saved=JSON.parse(localStorage.getItem(KEY)||'{}')||{};}catch{}
    let enabled=options.enabled!==false, minimized=saved.minimized===true, disposed=false;
    let timer=null, request=null, lastData=null, selected=typeof saved.gpu==='string'?saved.gpu:'';
    let position=Number.isFinite(saved.x)&&Number.isFinite(saved.y)?{x:saved.x,y:saved.y}:null;
    let expandedPosition=Number.isFinite(saved.expandedPosition?.x)&&Number.isFinite(saved.expandedPosition?.y)?{...saved.expandedPosition}:null;
    const style=document.createElement('style');style.textContent=css;document.head.append(style);
    const root=document.createElement('aside');root.className='mmx-hardware';root.setAttribute('aria-label','Server hardware monitor');
    root.innerHTML=`<header><button class="mmx-hardware-drag" title="Drag to move; arrow keys also move the monitor" aria-label="Move hardware monitor">⠿ Server monitor</button><button class="mmx-hardware-collapse" title="Minimize monitor" aria-label="Minimize hardware monitor">−</button></header><div class="mmx-hardware-body"><span class="mmx-hardware-device">ComfyUI server</span><select aria-label="Monitored GPU" hidden></select><div class="mmx-hardware-meters"></div><footer><span class="mmx-hardware-dot"></span><span class="mmx-hardware-status">Connecting…</span></footer></div>`;
    const body=root.querySelector('.mmx-hardware-body'), handle=root.querySelector('.mmx-hardware-drag'), collapse=root.querySelector('.mmx-hardware-collapse');
    const device=root.querySelector('.mmx-hardware-device'), selector=root.querySelector('select'), status=root.querySelector('.mmx-hardware-status');
    const meters={};
    for(const [key,label,color] of [['cpu','CPU','#8fbaff'],['gpu','GPU','#ab9cf5'],['vram','VRAM','#72d5bd'],['shared','Shared GPU RAM','#e7bb7a']]){
        const row=document.createElement('div');row.className='mmx-hardware-row';row.style.setProperty('--meter-color',color);
        row.innerHTML=`<div class="mmx-hardware-label"><span>${label}</span><span class="mmx-hardware-value">—</span></div><div class="mmx-hardware-track"><div class="mmx-hardware-fill"></div></div>`;
        row.title=key==='cpu'?'CPU usage on the ComfyUI server host':key==='shared'?'System RAM resident in GPU aperture segments, read directly from WSL. Includes all applications; it is not ordinary container RAM. A dash means the driver does not expose this metric.':'Server GPU readings include other applications on that GPU';
        root.querySelector('.mmx-hardware-meters').append(row);meters[key]={value:row.querySelector('.mmx-hardware-value'),fill:row.querySelector('.mmx-hardware-fill')};
    }
    document.body.append(root);
    const persist=()=>{try{localStorage.setItem(KEY,JSON.stringify({...position,expandedPosition,minimized,gpu:selected}));}catch{}};
    function place(x=position?.x ?? innerWidth-282,y=position?.y ?? innerHeight-252){
        const box=root.getBoundingClientRect();position={x:Math.max(8,Math.min(x,Math.max(8,innerWidth-(box.width||264)-8))),y:Math.max(8,Math.min(y,Math.max(8,innerHeight-(box.height||(minimized?42:230))-8)))};
        root.style.left=position.x+'px';root.style.top=position.y+'px';
    }
    const active=()=>enabled&&!minimized&&!document.hidden&&!disposed;
    const valid=n=>typeof n==='number'&&Number.isFinite(n)&&n>=0;
    function meter(key,value,text){meters[key].value.textContent=text;meters[key].fill.style.width=(valid(value)?Math.min(100,value):0)+'%';}
    function render(data){
        const gpus=Array.isArray(data.gpus)?data.gpus:[];
        const gpu=gpus.find(g=>g.id===selected)||gpus[0];if(gpu)selected=gpu.id;
        selector.replaceChildren();for(const g of gpus){const option=document.createElement('option');option.value=g.id;option.textContent=g.name;option.selected=g.id===selected;selector.append(option);}
        selector.hidden=gpus.length<2;device.hidden=gpus.length>1;
        device.textContent=gpu?.name?.replace(/^NVIDIA GeForce /,'')||'ComfyUI server';device.title=gpu?.name||'Metrics come from the ComfyUI server, not this browser';
        meter('cpu',data.cpu_percent,valid(data.cpu_percent)?`${Math.round(data.cpu_percent)}%`:'—');
        meter('gpu',gpu?.percent,valid(gpu?.percent)?`${Math.round(gpu.percent)}%`:'—');
        const used=gpu?.memory_used,total=gpu?.memory_total,available=valid(used)&&valid(total)&&total>0;
        meter('vram',available?used/total*100:null,available?`${(used/1073741824).toFixed(1)} / ${(total/1073741824).toFixed(1)} GiB`:'—');
        const sharedUsed=gpu?.shared_memory_used,sharedTotal=gpu?.shared_memory_total;
        const sharedAvailable=valid(sharedUsed)&&valid(sharedTotal)&&sharedTotal>0;
        meter('shared',sharedAvailable?sharedUsed/sharedTotal*100:null,sharedAvailable?`${(sharedUsed/1073741824).toFixed(1)} / ${(sharedTotal/1073741824).toFixed(1)} GiB`:'—');
        root.dataset.state='live';status.textContent=data.gpu_error||(!valid(data.cpu_percent)?'Sampling CPU…':'Live · ComfyUI server');
        status.title='Updates every 2 seconds while visible. GPU and VRAM use driver telemetry.';persist();
    }
    function stop(){clearTimeout(timer);timer=null;const prior=request;request=null;prior?.abort();}
    async function poll(){
        if(!active()||request)return;
        const controller=new AbortController();request=controller;
        const timeout=setTimeout(()=>controller.abort(),5000);
        try{
            const response=await client.fetchApi('/minimax_director/hardware',{signal:controller.signal});
            if(!response.ok)throw Error('Telemetry unavailable');
            const data=await response.json();if(request!==controller||!active())return;
            if(!data||!Array.isArray(data.gpus))throw Error('Invalid telemetry');
            lastData=data;render(data);
        }catch{
            if(request!==controller||!active())return;
            root.dataset.state='offline';status.textContent='Disconnected · retrying';status.title='Displayed readings may be out of date';
        }finally{
            clearTimeout(timeout);if(request===controller){request=null;if(active())timer=setTimeout(poll,2000);}
        }
    }
    function wake(){stop();if(active())poll();}
    function update(){root.hidden=!enabled;body.hidden=minimized;root.dataset.minimized=String(minimized);collapse.textContent=minimized?'+':'−';collapse.setAttribute('aria-label',minimized?'Expand hardware monitor':'Minimize hardware monitor');collapse.title=minimized?'Expand monitor':'Minimize monitor';place();wake();}
    collapse.onclick=()=>{
        const before=root.getBoundingClientRect();
        const shrinking=!minimized;
        if(!minimized)expandedPosition={...position};
        else if(expandedPosition)position={...expandedPosition};
        minimized=!minimized;update();
        // Shrink toward the right edge, keeping the toggle under the pointer.
        if(shrinking)place(expandedPosition.x+before.width-root.getBoundingClientRect().width,expandedPosition.y);
        persist();
    };
    selector.onchange=()=>{selected=selector.value;if(lastData)render(lastData);};
    let drag=null;
    handle.onpointerdown=event=>{if(event.button!==0)return;event.preventDefault();drag={id:event.pointerId,x:event.clientX,y:event.clientY,start:{...position}};handle.setPointerCapture?.(event.pointerId);};
    handle.onpointermove=event=>{if(!drag||event.pointerId!==drag.id)return;place(drag.start.x+event.clientX-drag.x,drag.start.y+event.clientY-drag.y);};
    const finishDrag=()=>{if(!drag)return;drag=null;persist();};handle.onpointerup=finishDrag;handle.onpointercancel=finishDrag;handle.onlostpointercapture=finishDrag;
    handle.onkeydown=event=>{const delta={ArrowLeft:[-10,0],ArrowRight:[10,0],ArrowUp:[0,-10],ArrowDown:[0,10]}[event.key];if(!delta)return;event.preventDefault();event.stopPropagation();place(position.x+delta[0],position.y+delta[1]);persist();};
    const resized=()=>{place();persist();};
    document.addEventListener('visibilitychange',wake);window.addEventListener('resize',resized);
    root.addEventListener('pointerdown',event=>event.stopPropagation());root.addEventListener('wheel',event=>event.stopPropagation());
    update();
    return {element:root,setEnabled(value){enabled=!!value;update();},destroy(){disposed=true;stop();document.removeEventListener('visibilitychange',wake);window.removeEventListener('resize',resized);root.remove();style.remove();}};
}

let overlay=null, enabled=true;
app.registerExtension({
    name:'MiniMaxH3.HardwareMonitor',
    settings:[{id:SETTING,name:'Show hardware monitor',type:'boolean',defaultValue:true,category:['MiniMax H3','Monitor','Visible'],
        tooltip:'Floating CPU, GPU and VRAM usage for the ComfyUI server. Drag to move or minimize to pause.',onChange(value){enabled=!!value;overlay?.setEnabled(enabled);}}],
    setup(){overlay?.destroy();overlay=createHardwareMonitor(api,{enabled});}
});
