"""One typed timeline boundary for external authoring and the Master."""
import copy
from .project import migrate_timeline
from .cache_manager import fingerprint_value


def merge_authored_timeline(local, authored):
    if not isinstance(authored, dict) or not isinstance(authored.get('clips'), list):
        raise ValueError('Connected Timeline Builder must supply a clips list.')
    state = migrate_timeline(local)
    previous = {row['id']: row for row in state['clips'] if row.get('id')}
    incoming = migrate_timeline(authored)
    if incoming.get('project_id') and incoming['project_id'] != state.get('project_id'):
        previous = {}  # Never transplant approvals between different projects.
    ids = [row.get('id') for row in incoming['clips']]
    if not ids or any(not value for value in ids) or len(set(ids)) != len(ids):
        raise ValueError('External clips need stable unique IDs.')
    generation_keys = ('type', 'duration', 'prompt', 'ref_ids')
    shared_changed = any(key in authored and incoming.get(key) != state.get(key)
                         for key in ('shared_prompt', 'shared_prompt_policy', 'shared_ref_ids'))
    invalidate_chain = False
    for row in incoming['clips']:
        saved = previous.get(row['id'], {})
        for key,value in saved.items():
            if key not in ('id','name','type','duration','prompt','ref_ids','group','authoring_owner'):
                row[key]=value
        signature = fingerprint_value(row.get('group'))
        changed = bool(saved) and (any(row.get(key) != saved.get(key) for key in generation_keys)
            or saved.get('authored_group_signature') is not None and saved['authored_group_signature'] != signature)
        row['authored_group_signature'] = signature
        independent = row.get('locked') or row.get('source') or row.get('continuity') is False or row.get('continuity_mode', 'Independent (No Continuity)') == 'Independent (No Continuity)'
        invalidate_chain = changed or shared_changed or (invalidate_chain and not independent)
        if invalidate_chain and not row.get('locked'):
            row['validated'] = False
            row['refine_approved'] = False
            row['refine_pending'] = False
            row['invalidated_generation'] = saved.get('invalidated_generation') or saved.get('generation')
        row['authoring_owner'] = 'Timeline Builder'
    # External authors own reference/prompt metadata, while the Master retains
    # execution state and approvals for existing stable clip identities.
    for key in ('project_id','project_name','references','available_refs','refmods',
                'shared_prompt','shared_prompt_policy','cast_cards','imported_prompt_history',
                'shared_ref_ids','import_bindings','source_clip_ids','imported_take_ids',
                'audio_fade_ms','audio_gain_match'):
        if key in authored:state[key]=copy.deepcopy(incoming[key])
    state['clips'] = incoming['clips']
    state['timeline_owner'] = 'Timeline Builder'
    return state


def groups_to_timeline(groups, owner='builder'):
    clips = []
    for index, group in enumerate(groups):
        kind = group.get('kind', 'REF2VA')
        if kind == 'FL2VA':
            kind = 'FL2VA' if group.get('last_frame') is not None and group.get('first_frame') is not None else 'L2VA' if group.get('last_frame') is not None else 'I2VA' if group.get('first_frame') is not None else 'T2VA'
        clips.append({'id': f"group_{group.get('_builder_id') or owner+'_'+str(index)}",
            'name': group.get('name', f'Clip {index+1}'), 'type': kind,
            'duration': group.get('duration_sec', 5), 'prompt': group.get('prompt', ''),
            'group': group, 'continuity': False, 'continuity_mode':'Independent (No Continuity)'})
    return {'version':2, 'approval_control_version':1, 'clips':clips}
