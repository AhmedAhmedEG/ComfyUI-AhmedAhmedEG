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
    if(/^Encoding reference /i.test(label))return 'Encoding References';
    let lora=/^LoRA · (reading|applying) (.+)$/i.exec(label);
    if(lora)return `${lora[1].toLowerCase()==='reading'?'Loading':'Applying'} LoRA ${lora[2].replace(/\.safetensors$/i,'')}`;
    if(/^LoRA · \d+ ready$/i.test(label))return 'LoRAs Ready';
    const names={
        'Checking reference cache':'Checking Cache',
        'Loading cached reference encodings':'Loading References',
        'Saved clip reused':'Reusing Saved Clip',
        'Reading project and settings':'Reading Project',
        'Preparing clip and references':'Checking Cache',
        'Checking model and asset fingerprints':'Checking Cache',
        'Preparing clip LoRAs':'Loading LoRAs',
        'Preparing MiniMax H3 model configuration':'Loading MiniMax H3',
        'Preparing H3 model for sampling':'Loading MiniMax H3',
        'H3 model · loading as needed and initializing sampler':'Loading MiniMax H3',
        'H3 model · loading as needed and applying LoRA weights':'Loading MiniMax H3 + LoRA',
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
    // Stages without a step count (model loads, VAE decode, saving) have no
    // measurable progress; show live activity instead of a frozen bar.
    const spinner=document.createElement('span');spinner.className='mmx-stage-spinner';spinner.setAttribute('aria-hidden','true');
    const text=document.createElement('span');
    detail.append(spinner,text);
    if(!document.getElementById('mmx-stage-progress-style')){
        const style=document.createElement('style');style.id='mmx-stage-progress-style';
        style.textContent='@keyframes mmx-stage-spin{to{transform:rotate(360deg)}}@keyframes mmx-stage-busy{from{background-position:0 0}to{background-position:40px 0}}'+
            '.mmx-stage-spinner{display:inline-block;width:.8em;height:.8em;margin:0 5px -1px 0;border:2px solid currentColor;border-right-color:transparent;border-radius:50%;animation:mmx-stage-spin .8s linear infinite;box-sizing:border-box}'+
            '.mmx-stage-detail[data-counted=true] .mmx-stage-spinner{display:none}'+
            'rgthree-progress-bar.mmx-stage-busy{background-image:repeating-linear-gradient(-45deg,rgba(255,255,255,.10) 0 10px,transparent 10px 20px);background-size:40px 100%;animation:mmx-stage-busy 1s linear infinite}';
        document.head.append(style);
    }
    function attach(){
        const next=document.querySelector('rgthree-progress-bar');
        const text=next?.progressTextEl || next?.shadowRoot?.querySelector('[part="text"]');
        if(next===bar && text===target)return;
        observer?.disconnect();detail.remove();if(bar!==next)bar?.classList?.remove('mmx-stage-busy');bar=next;target=text;
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
        if(bar.currentPromptExecution?.errorDetails || activeNode!=null && String(activeNode).split(':').at(-1)!==ours){detail.remove();bar.classList?.remove('mmx-stage-busy');return;}
        const clip=current.clipName?`${current.clipName} · `:'';
        const counted=Number.isFinite(current.step) && Number(current.steps)>0;
        const sampling=current.label==='Sampling H3';
        const steps=counted?(sampling?` · Step ${current.step}/${current.steps}`:` · ${current.step}/${current.steps}`):'';
        const value=`· ${clip}${shortStage(current.label)}${steps} · ${Math.floor((Date.now()-started)/1000)}s`;
        if(text.textContent!==value){text.textContent=value;detail.title=value;}
        detail.dataset.counted=String(counted);
        bar.classList?.toggle('mmx-stage-busy',!counted);
        if(detail.parentNode!==target)target.append(detail);
    }
    function clear(){current=null;clearInterval(timer);timer=null;observer?.disconnect();observer=null;detail.remove();bar?.classList?.remove('mmx-stage-busy');bar=target=null;}
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
