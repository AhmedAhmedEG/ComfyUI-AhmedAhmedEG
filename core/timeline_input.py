"""One typed timeline boundary for external authoring and the Master."""
import copy
from .project import migrate_timeline


def merge_authored_timeline(local, authored):
    if not isinstance(authored, dict) or not isinstance(authored.get('clips'), list):
        raise ValueError('Connected Timeline Builder must supply a clips list.')
    state = migrate_timeline(local)
    previous = {row['id']: row for row in state['clips'] if row.get('id')}
    incoming = migrate_timeline(authored)
    ids = [row.get('id') for row in incoming['clips']]
    if not ids or any(not value for value in ids) or len(set(ids)) != len(ids):
        raise ValueError('External clips need stable unique IDs.')
    for row in incoming['clips']:
        saved = previous.get(row['id'], {})
        for key,value in saved.items():
            if key not in ('id','name','type','duration','prompt','ref_ids','group','authoring_owner'):
                row[key]=value
        row['authoring_owner'] = 'Timeline Builder'
    if 'references' in incoming: state['references']=incoming['references']
    if 'shared_prompt' in incoming: state['shared_prompt']=incoming['shared_prompt']
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
