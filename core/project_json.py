"""Editable project JSON: authoring data and graph, never generated tensors."""
import copy
import json
import math
import uuid

from .project import migrate_timeline, export_timeline_state


CLIP_RUNTIME = {'selected','last_seed','last_seed_mode','generation','saved_generation',
    'validated_generation','invalidated_generation','cache_report','refine_pending',
    'refine_approved','refine_approved_generation','authored_group_signature','authoring_owner'}
TIMELINE_RUNTIME = {'available_refs','draft_updated_at','server_revision','run_selection',
    'approval_control_version','timeline_owner','source_clip_ids','imported_take_ids'}


def authoring_timeline(value):
    state=migrate_timeline(export_timeline_state(value))
    for key in TIMELINE_RUNTIME:state.pop(key,None)
    for clip in state['clips']:
        for key in CLIP_RUNTIME:clip.pop(key,None)
    builder=state.get('builder_state')
    if isinstance(builder,str):state['builder_state']=json.loads(builder or '{}')
    return state


def prepare_workflow(workflow, master_id, timeline=None):
    if not isinstance(workflow,dict) or not isinstance(workflow.get('nodes'),list):
        raise ValueError('Project workflow must contain a nodes list.')
    graph=copy.deepcopy(workflow)
    master=next((row for row in graph['nodes'] if str(row.get('id'))==str(master_id)
        and row.get('type') in ('MiniMaxH3MasterNode','MiniMaxH3MasterDirector')),None)
    if master is None:raise ValueError('Project workflow is missing its Master node.')
    named=master.setdefault('widgets_values_named',{})
    for key in ('timeline_data','builder_state','generation_mode'):named.pop(key,None)
    master['widgets_values']=[]
    if timeline is not None:
        state=copy.deepcopy(timeline);builder=state.pop('builder_state',{})
        mode={'Next shot':'Next clip','All shots':'All clips'}.get(state.get('generation_mode'),state.get('generation_mode','Next clip'))
        named.update(timeline_data=json.dumps(state),builder_state=builder if isinstance(builder,str) else json.dumps(builder),generation_mode=mode)
        master['widgets_values']=[mode,named['timeline_data'],named['builder_state']]
    return graph


def restore_timeline(manager, document, reference_catalog=None):
    from .cache_manager import safe_component
    state=copy.deepcopy(document['timeline'])
    state['approval_control_version']=1
    state=migrate_timeline(state)
    seen=set()
    manager._manifest=manager._load_manifest()
    bindings=document.get('result_bindings') or document.get('server_cache_manifest') or {}
    catalog=document.get('reference_catalog',[]) if reference_catalog is None else reference_catalog
    by_name={}
    for row in catalog:
        name=row.get('name') or row.get('id')
        if name:by_name.setdefault(name,[]).append(row.get('id'))
    for clip in state['clips']:
        if not clip.get('id'):
            clip['id']='clip_'+uuid.uuid4().hex;clip['validated']=False
        cid=safe_component(clip['id'])
        if cid in seen:raise ValueError(f'Duplicate clip ID: {cid}. Give each clip a unique ID or omit it.')
        seen.add(cid);clip['id']=cid
        names=clip.pop('ref_names',None)
        if names is not None:
            if not isinstance(names,list) or any(not isinstance(name,str) for name in names):
                raise ValueError(f'Clip {cid}: ref_names must be a list of reference names.')
            resolved=[]
            for name in names:
                choices=by_name.get(name,[])
                if len(choices)!=1:raise ValueError(f'Reference {name!r} is missing or ambiguous. Add exactly one asset with that name to the pool before importing.')
                resolved.append(choices[0])
            clip['ref_ids']=list(dict.fromkeys([*resolved,*clip.get('ref_ids',[])]))
        duration=clip.get('duration',5)
        if isinstance(duration,bool) or not isinstance(duration,(int,float)) or not math.isfinite(duration) or duration<=0:
            raise ValueError(f'Clip {cid}: duration must be positive seconds.')
        clip['duration']=duration
        saved=manager._manifest.get('clips',{}).get(cid,{})
        binding=bindings.get(cid,{})
        if clip.get('validated'):
            # Bind approval to the exported take, never silently approve a
            # different generation just because its clip ID happens to match.
            expected=clip.get('validated_generation') or binding.get('generation')
            if not expected and binding.get('fingerprint')==saved.get('fingerprint') and saved.get('fingerprint'):
                expected=saved.get('generation')
            clip['validated_generation']=expected or 'missing-imported-result'
    state['project_id']=manager.project_id
    return state
