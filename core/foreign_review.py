"""Recover explicit authoring/history/loader identities without executing a foreign graph."""
import copy
import json
import re


def recover_workflow(data):
    workflow = data.get('workflow', data)
    if not isinstance(workflow, dict) or not isinstance(workflow.get('nodes'), list):
        return data, []
    candidates = []
    for node in workflow['nodes']:
        if not re.search(r'(?:Director|Extender|MiniMaxH3MasterNode)', str(node.get('type', ''))):
            continue
        named = node.get('widgets_values_named', {})
        values = list(named.values()) or node.get('widgets_values', [])
        parsed = []
        for value in values:
            if isinstance(value, str) and value.lstrip().startswith('{'):
                try:
                    value = json.loads(value)
                except ValueError:
                    continue
            if isinstance(value, dict):
                parsed.append(value)
        timeline = next((v for v in parsed if any(isinstance(v.get(k), list) for k in ('items', 'clips', 'segments', 'shots'))), None)
        if timeline is not None:
            candidates.append((node, named, timeline, parsed))
    if len(candidates) != 1:
        raise ValueError('Workflow import needs exactly one recognized Director/Extender timeline; export the intended project when several are present.')
    node, named, timeline, parsed = candidates[0]
    notices = []
    if 'Extender' in node['type']:
        refs = next((v for v in parsed if isinstance(v.get('refs'), list)), {'refs': []})
        result = {'extender': {**named, 'clips_json': timeline, 'refs_json': refs}}
    elif 'items' in timeline:
        result = {**timeline, 'dasiwa_minimax_h3_reference_pack': True,
                  'model_mode': named.get('mode', timeline.get('builder_state', {}).get('mode', 'REF2VA')),
                  'prompt': named.get('prompt') or timeline.get('resolved_prompt') or '', 'settings': named}
    else:
        result = {**timeline, 'widgets': named}
    result['imported_prompt_history'] = node.get('properties', {}).get('dasiwaH3ForgeHistory', [])
    result['cast_cards'] = timeline.get('cast_cards', {})
    bindings = {}
    for loader in workflow['nodes']:
        if loader.get('type') != 'UNETLoader':
            continue
        widgets = loader.get('widgets_values_named', {})
        values = loader.get('widgets_values', [])
        name = widgets.get('unet_name') or (values[0] if values else '')
        if name:
            bindings['workflow_model_'+str(loader['id'])] = {'filename': name, 'weight_dtype': widgets.get('weight_dtype', values[1] if len(values)>1 else 'default')}
    result['model_bindings'] = bindings
    if not named:
        notices.append('Recovered serialized timeline from workflow widgets. Unnamed numeric widget positions were not guessed; review Settings.')
    notices.append('Installed checkpoint filenames recovered as named model-pack aliases. Arbitrary procedural graph patches are not executed; review connections before using a binding.')
    return result, notices


def reference_metadata(row):
    from .cast_tools import boxes_of
    from .forge_cast import reference_roles
    label = str(row.get('forge_label', ''))
    who = row.get('characters', row.get('forge_who', []))
    if isinstance(who, str):
        who = [int(v) for v in who.split(',') if v.strip()]
    if not who and label.startswith('character-'):
        who = [int(label[10:])]
    if not who and label.startswith('group-'):
        who = [int(v) for v in label[6:]]
    role = row.get('role', row.get('forge_role', 'subject'))
    if label in ('place', 'style', 'pose'):
        role = label
    return {'roles': reference_roles({**row,'role':role}), 'characters': who, 'boxes': boxes_of(row.get('boxes', row.get('people_boxes'))),
            'position': row.get('position', {'y':'top-to-bottom','z':'front-to-back','none':'unspecified'}.get(row.get('forge_who_axis'),'left-to-right' if len(who)>1 else 'unspecified')),
            'retention': row.get('retention', 'fully_preserved'), 'forge_include': row.get('forge_include', row.get('enabled', True)) is not False,
            'role': role, 'description': '\n'.join(str(v) for v in [row.get('description', row.get('forge_instructions', '')),
                ('Keep: '+str(row['forge_keep'])) if row.get('forge_keep') else '',
                ('Exclude: '+str(row['forge_drop'])) if row.get('forge_drop') else ''] if v)}


def reviewed_history(data):
    raw = data.get('imported_prompt_history', data.get('forge_history', data.get('properties', {}).get('dasiwaH3ForgeHistory', [])))
    if not isinstance(raw, list):
        raise ValueError('Imported prompt history must be a list.')
    result = []
    for row in raw[:20]:
        if not isinstance(row, dict):
            continue
        prompt = row.get('simple_prompt', row.get('prompt', ''))
        if not isinstance(prompt, str) or not prompt.strip():
            continue
        if len(prompt)>100000:
            raise ValueError('Imported prompt history entry is too large.')
        result.append({'prompt': prompt, 'type': row.get('mode', row.get('type', 'REF2VA')),
            'fields': copy.deepcopy(row.get('fields', {})), 'reference_snapshot': copy.deepcopy(row.get('reference_snapshot', {})),
            'brief': str(row.get('brief', ''))[:4000], 'source_created': row.get('createdAt'),
            'reference_mapping_verified': False})
    return result
