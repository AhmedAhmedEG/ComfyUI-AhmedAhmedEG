import {app} from "../../scripts/app.js";
import {api} from "../../scripts/api.js";

export function createStageProgress(client){
    const root=document.createElement('div');root.className='mmx-stage-progress';root.hidden=true;
    root.setAttribute('role','status');root.setAttribute('aria-live','polite');
    const style=document.createElement('style');
    style.textContent='.mmx-stage-progress{position:fixed;z-index:1300;top:6px;left:50%;transform:translateX(-50%);max-width:calc(100vw - 24px);padding:6px 12px;border:1px solid #56708d;border-radius:7px;background:#172331f5;color:#e6eef9;font:12px system-ui,sans-serif;box-shadow:0 2px 8px #0004;pointer-events:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.mmx-stage-progress[hidden]{display:none}.mmx-stage-progress::before{content:"";display:inline-block;width:6px;height:6px;margin-right:8px;border-radius:50%;background:#8bc5ff}';
    document.head.append(style);document.body.append(root);
    let current=null,started=0,timer=null;
    function draw(){
        if(!current || document.hidden)return;
        const clip=current.index?`Clip ${current.index}${current.total?'/'+current.total:''} · `:'';
        const steps=Number.isFinite(current.step)?` · Step ${current.step}/${current.steps}`:'';
        root.textContent=`H3 · ${clip}${current.label}${steps} · ${Math.floor((Date.now()-started)/1000)}s`;
        root.title=root.textContent;
    }
    function clear(){current=null;root.hidden=true;clearInterval(timer);timer=null;}
    function update(event){
        const value=event.detail;
        if(!value || typeof value.label!=='string' || !value.node)return;
        if(!value.active){if(current?.node===value.node)clear();return;}
        if(!current || current.node!==value.node || current.label!==value.label || current.clip_id!==value.clip_id)started=Date.now();
        current=value;root.hidden=false;draw();
        timer ||= setInterval(draw,1000);
    }
    function executing(event){if(event.detail===null || event.detail?.node===null)clear();}
    client.addEventListener('minimax_director/stage',update);
    client.addEventListener('executing',executing);
    for(const name of ['execution_start','execution_error','execution_interrupted'])client.addEventListener(name,clear);
    return {element:root,destroy(){clear();root.remove();style.remove();client.removeEventListener('minimax_director/stage',update);client.removeEventListener('executing',executing);for(const name of ['execution_start','execution_error','execution_interrupted'])client.removeEventListener(name,clear);}};
}

let indicator;
app.registerExtension({name:'MiniMaxH3.StageProgress',setup(){indicator?.destroy();indicator=createStageProgress(api);}});
