import {app} from "../../scripts/app.js";
import {api} from "../../scripts/api.js";

// Extend the existing rgthree green bar, without replacing its text, percentages,
// rendering method or prompt-service state. No standalone progress UI is created.
function shortStage(label){
    if(/video\s*vae/i.test(label))return /decod/i.test(label)?'Decoding Video':'Encoding References';
    if(/audio\s*vae/i.test(label))return /decod/i.test(label)?'Decoding Audio':'Encoding References';
    if(/^Text encoder/i.test(label))return 'Text Conditioning';
    if(/^Text conditioning/i.test(label))return 'Text Conditioning';
    if(/^Preparing reference /i.test(label))return 'Checking Cache';
    const names={
        'Checking reference cache':'Checking Cache',
        'Loading cached reference encodings':'Loading References',
        'Saved clip reused':'Reusing Saved Clip',
        'Reading project and settings':'Reading Project',
        'Preparing clip and references':'Checking Cache',
        'Checking model and asset fingerprints':'Checking Cache',
        'Preparing H3 model and clip LoRA configuration':'Loading MiniMax H3',
        'Preparing H3 model for sampling':'Loading MiniMax H3',
        'H3 model · loading as needed and initializing sampler':'Loading MiniMax H3',
        'Preparing latent and sampling noise':'Preparing Sampling',
        'Sampling H3':'Sampling',
        'Refining clip':'Refining',
        'Decoding generated video and audio':'Decoding Video / Audio',
        'Refining faces':'Refining Faces',
        'Clip saved':'Saved',
        'First pass saved — waiting for approval':'Awaiting Approval',
        'Saving clip latents, audio and frames':'Saving Clip',
        'Assembling output video and joining audio':'Assembling Video',
        'Releasing temporary buffers':'Cleanup'
    };
    return names[label] || label.split(' · ')[0];
}
export function createStageProgress(client){
    let current=null,started=0,timer=null,bar=null,target=null,observer=null;
    const detail=document.createElement('span');
    detail.className='mmx-stage-detail';
    detail.style.cssText='white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0;margin-left:6px';
    function attach(){
        const next=document.querySelector('rgthree-progress-bar');
        const text=next?.progressTextEl || next?.shadowRoot?.querySelector('[part="text"]');
        if(next===bar && text===target)return;
        observer?.disconnect();detail.remove();bar=next;target=text;
        if(target){
            // rgthree replaces its text on every native progress update. Observe
            // that element only and restore our suffix after its own render.
            observer=new MutationObserver(draw);
            observer.observe(target,{childList:true,subtree:true,characterData:true});
        }
    }
    function draw(){
        if(!current || document.hidden)return;
        attach();
        if(!target)return;
        const activeNode=bar.currentNodeId;
        const ours=String(current.node).split(':').at(-1);
        if(bar.currentPromptExecution?.errorDetails || activeNode!=null && String(activeNode).split(':').at(-1)!==ours){detail.remove();return;}
        const clip=current.clipName?`${current.clipName} · `:'';
        const steps=Number.isFinite(current.step)?` · Step ${current.step}/${current.steps}`:'';
        const text=`· ${clip}${shortStage(current.label)}${steps} · ${Math.floor((Date.now()-started)/1000)}s`;
        if(detail.textContent!==text){detail.textContent=text;detail.title=text;}
        if(detail.parentNode!==target)target.append(detail);
    }
    function clear(){current=null;clearInterval(timer);timer=null;observer?.disconnect();observer=null;detail.remove();bar=target=null;}
    function update(event){
        const value=event.detail;
        if(!value || typeof value.label!=='string' || !value.node)return;
        if(!value.active){if(current?.node===value.node)clear();return;}
        if(!current || current.node!==value.node || current.label!==value.label || current.clip_id!==value.clip_id)started=Date.now();
        let clipName=value.clip_name || '';
        if(!clipName && value.clip_id){
            if(current?.node===value.node && current.clip_id===value.clip_id)clipName=current.clipName || '';
            if(!clipName)try{
                const node=app.graph?.getNodeById(String(value.node).split(':').at(-1));
                const raw=node?.widgets?.find(widget=>widget.name==='timeline_data')?.value;
                const timeline=typeof raw==='string'?JSON.parse(raw):raw;
                clipName=timeline?.clips?.find(clip=>String(clip.id)===String(value.clip_id))?.name || '';
            }catch{}
        }
        current={...value,clipName};draw();timer ||= setInterval(draw,1000);
    }
    function executing(event){if(event.detail===null || event.detail?.node===null)clear();}
    client.addEventListener('minimax_director/stage',update);
    client.addEventListener('executing',executing);
    for(const name of ['execution_start','execution_error','execution_interrupted'])client.addEventListener(name,clear);
    return {destroy(){clear();client.removeEventListener('minimax_director/stage',update);client.removeEventListener('executing',executing);for(const name of ['execution_start','execution_error','execution_interrupted'])client.removeEventListener(name,clear);}};
}

let indicator;
app.registerExtension({name:'MiniMaxH3.StageProgress',setup(){indicator?.destroy();indicator=createStageProgress(api);}});
