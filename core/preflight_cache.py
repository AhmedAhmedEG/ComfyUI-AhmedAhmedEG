"""Read-only unchanged-result checks before requesting lazy diffusion models."""
import inspect
import hashlib
import json
from pathlib import Path

from .cache_manager import fingerprint_value,safe_component
from .provenance import file_provenance,record_graph_provenance,runtime_provenance


class UnsupportedGraph(ValueError):pass


def model_graph_signature(graph,link,seen=None):
    """Describe known deterministic model wiring without evaluating its nodes."""
    if not isinstance(link,(list,tuple)) or len(link)!=2:raise UnsupportedGraph('Missing model connection')
    seen=set() if seen is None else seen
    node_id=str(link[0])
    if node_id in seen:raise UnsupportedGraph('Cyclic model wiring')
    seen.add(node_id)
    try:
        node=graph[node_id];kind=node['class_type'];inputs=node.get('inputs',{})
        allowed={'UNETLoader','LoraLoaderModelOnly','H3SLAAttention','ComfySwitchNode',
                 'PrimitiveBoolean','PrimitiveInt','PrimitiveFloat'}
        if kind not in allowed or link[1]!=0:raise UnsupportedGraph('Unknown model modifier')
        def value(item):
            if isinstance(item,(list,tuple)):
                return model_graph_signature(graph,item,seen)
            if item is None or isinstance(item,(str,int,float,bool)):return item
            raise UnsupportedGraph('Unknown model setting')
        if kind=='ComfySwitchNode':
            switch=inputs['switch']
            if isinstance(switch,(list,tuple)):
                control=graph[str(switch[0])]
                if control['class_type']!='PrimitiveBoolean' or switch[1]!=0:raise UnsupportedGraph('Dynamic model switch')
                switch=control['inputs']['value']
            if not isinstance(switch,bool):raise UnsupportedGraph('Dynamic model switch')
            return {'type':kind,'switch':switch,'model':value(inputs['on_true' if switch else 'on_false'])}
        settings={key:value(item) for key,item in inputs.items()}
        if kind in ('UNETLoader','LoraLoaderModelOnly'):
            import folder_paths
            field,category=('unet_name','diffusion_models') if kind=='UNETLoader' else ('lora_name','loras')
            if not isinstance(inputs.get(field),str):raise UnsupportedGraph('Dynamic checkpoint filename')
            settings['weights']=file_provenance(folder_paths.get_full_path_or_raise(category,inputs[field]))
        # Include the installed modifier implementation when available.
        source=None
        try:
            import nodes
            cls=nodes.NODE_CLASS_MAPPINGS.get(kind)
            path=inspect.getsourcefile(cls) if cls is not None else None
            if path:source=file_provenance(path)
        except (ImportError,TypeError,OSError):pass
        return {'type':kind,'settings':settings,'implementation':source}
    finally:seen.remove(node_id)


class PreflightCache:
    def __init__(self,inputs,timeline):
        self.inputs=inputs
        self.timeline={**timeline,'clips':[dict(clip) for clip in timeline.get('clips',[])]}
        self.graph=inputs.get('prompt')
        self.node_id=str(inputs.get('unique_id','default_director'))
        self.project_id=str(timeline.get('project_id') or (inputs.get('config') or {}).get('project_id') or self.node_id)
        self.runtime=None

    def manifest(self):
        from .cache_manager import get_cache_root_dir
        root=Path(get_cache_root_dir(create=False))/safe_component(self.project_id)
        try:data=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):data={}
        return root,data

    def key(self,index):
        try:
            if not isinstance(self.graph,dict):return None
            shots=self.timeline.get('clips',[]);shot=shots[index]
            if shot.get('seed_mode','fixed')!='fixed' or self.inputs.get('model_pack'):
                return None
            from .task_modes import normalize_mode,get_required_model_type
            from .continuity import resolve_continuity
            config=self.inputs.get('config') or {}
            socket=get_required_model_type(normalize_mode(shot.get('type','T2V')))+'_model'
            signature=model_graph_signature(self.graph,self.graph[self.node_id]['inputs'][socket])
            active=self.inputs.get(socket)
            if active is not None:
                graph_key=fingerprint_value(signature)
                original=getattr(active,'_mmx_preflight_graph',None)
                if original is None:setattr(active,'_mmx_preflight_graph',graph_key)
                elif original!=graph_key:
                    # A stock loader may return its old live object after a
                    # checkpoint was overwritten. Do not bless new disk bytes
                    # as the identity of those old retained weights.
                    return None
            # These inputs are already evaluated; this never requests H3.
            record_graph_provenance(self.graph,self.node_id,**{name:self.inputs.get(name) for name in ('clip','video_vae','audio_vae')})
            encoder=self.inputs.get('clip');patcher=getattr(encoder,'patcher',None)
            if getattr(patcher,'forced_hooks',None) is not None or getattr(encoder,'apply_hooks_to_conds',None) is not None:return None
            from .text_conditioning_cache import framed_key
            encoder_settings={name:getattr(encoder,name,None) for name in ('layer_idx','use_clip_schedule','tokenizer_options')}
            encoder_settings['patcher']={name:getattr(patcher,name,None) for name in ('patches','object_patches','model_options')}
            encoder_signature=framed_key(encoder_settings,hashlib.sha256()).hexdigest()
            runtime_keys={'cache_report','validated','validated_generation','selected','last_seed','generation',
                'refine_pending','refine_approved','refine_approved_generation','invalidated_generation','last_seed_mode','name'}
            authored={k:v for k,v in shot.items() if k not in runtime_keys}
            refs=self.inputs.get('ref_pack') or {}
            ids=set([*self.timeline.get('shared_ref_ids',[]),*shot.get('ref_ids',[])])
            source=shot.get('source')
            if source and (not isinstance(source,dict) or source.get('filename') and not source.get('ref_id')):
                return None # File-source edits need the normal source decoder's provenance.
            if isinstance(source,dict) and source.get('ref_id'):ids.add(source['ref_id'])
            if 'refs' in refs:
                refs=[row for row in refs['refs'] if ids & {row.get(k) for k in ('id','alt_id','slot_id','ref_id')}]
            else:refs={k:v for k,v in refs.items() if k in ids}
            if self.timeline.get('refmods') or isinstance(refs,list) and any(row.get('type')=='refmod' for row in refs):
                return None # RefMod bundles can have companion metadata; use their full loader check.
            if (self.inputs.get('face_refine') or {}).get('enabled',False):return None
            from .loras import resolve_lora_files
            from .provenance import algorithm_provenance
            adapters=resolve_lora_files(shot.get('loras',[]))
            algorithms=algorithm_provenance(self.inputs.get('selflift'),self.inputs.get('refine'),self.inputs.get('semantic_bridge'))
            file_refs=[]
            for row in self.timeline.get('references',[]):
                if row.get('id') not in ids:continue
                from .media_io import resolve_input_path
                import folder_paths
                filename=str(row.get('filename') or row.get('file') or '')
                relative=str(Path(row.get('subfolder') or '')/filename)
                file_refs.append((row,file_provenance(resolve_input_path(relative,folder_paths.get_input_directory()))))
            shared={k:self.timeline[k] for k in ('audio_mode','continuity_redraw','refmods','resolution','shared_prompt',
                'shared_prompt_policy','shared_ref_ids','source_size','cast_cards') if k in self.timeline}
            ignored={'self','cls','model','fl2va_model','ref2va_model','prompt','unique_id','timeline_data','timeline',
                'generation_mode','ref_pack','config','kwargs','builder_state'}
            params={k:v for k,v in self.inputs.items() if k not in ignored and v is not None}
            builder=self.inputs.get('builder_state','{}')
            if isinstance(builder,str):builder=json.loads(builder or '{}')
            settings={k:v for k,v in config.items() if k not in ('run_mode','generation_mode','decoded_output','preview_mode')}
            continuity=resolve_continuity(shot,self.inputs.get('continuity_mode',config.get('continuity_mode','Motion Context (Chained)')),
                self.inputs.get('context_length',config.get('context_length','22')))
            _,manifest=self.manifest()
            upstream=None
            if index and continuity['mode']!='Independent (No Continuity)':
                previous=manifest.get('clips',{}).get(str(shots[index-1]['id']),{})
                upstream=(previous.get('generation'),previous.get('fingerprint'))
            self.runtime=self.runtime or runtime_provenance()
            return fingerprint_value({'version':1,'runtime':self.runtime,'clip':authored,'model':signature,
                'settings':settings,'params':params,'builder':builder,'shared':shared,'refs':refs,'files':file_refs,
                'adapters':adapters,'algorithm_weights':algorithms,'encoder_options':encoder_signature,
                'prefix':[(c.get('id'),c.get('duration')) for c in shots[:index]],'upstream':upstream})
        except (ValueError,KeyError,TypeError,OSError,AttributeError,IndexError):
            return None # Unknown wiring/data needs the full generation-input check.

    def matches(self,index):
        key=self.key(index)
        if key is None:return False
        root,manifest=self.manifest();cid=str(self.timeline['clips'][index]['id'])
        meta=manifest.get('clips',{}).get(cid,{})
        if meta.get('preflight_key')!=key:return False
        generation=meta.get('generation')
        if not generation:return False
        # Resolve the native artifact names without constructing a project/cache.
        from .cache_manager import ProjectCacheManager
        manager=ProjectCacheManager.__new__(ProjectCacheManager)
        manager.project_dir=str(root);manager._manifest=manifest
        return all(Path(manager._clip_artifact_path(cid,kind,generation)).is_file() for kind in ('latent','frames','audio'))
