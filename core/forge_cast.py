"""Pack-owned cast metadata and clip-local native labels for prompt drafting."""
import re

RETENTION=('fully_preserved','partially_preserved','attribute_transfer','weak_reference')


def cast_metadata(settings):
    raw=settings.get('characters') or []
    if isinstance(raw,str):raw=[v.strip() for v in raw.split(',') if v.strip()]
    from .cast_tools import boxes_of
    boxes=boxes_of(settings.get('boxes'))
    characters=list(dict.fromkeys([*[int(v) for v in raw],*[r['n'] for r in sorted(boxes,key=lambda r:r['box'][0]+r['box'][2])]]))
    if len(characters)>32 or len(set(characters))!=len(characters) or any(not 1<=v<=99 for v in characters):
        raise ValueError('Cast references accept up to 32 distinct Character numbers from 1 to 99.')
    position=settings.get('position') or 'unspecified'
    if position not in ('unspecified','left','centre','right','left-to-right','top-to-bottom','front-to-back'):raise ValueError('Unknown cast position.')
    retention=settings.get('retention') or 'fully_preserved'
    if retention not in RETENTION:raise ValueError('Unknown visual retention policy.')
    return dict(boxes=boxes,characters=characters,position=position,retention=retention,forge_include=settings.get('forge_include',True) is not False)


def clip_bindings(state, clip):
    pool={r['id']:r for r in [*state.get('references',[]),*state.get('available_refs',[])] if r.get('id')}
    ids=list(dict.fromkeys([*state.get('shared_ref_ids',[]),*clip.get('ref_ids',[])]))
    counts={};result=[]
    for rid in ids:
        row=pool.get(rid)
        if not row:continue
        kind=row.get('type');name={'image':'Picture','video':'Video','audio':'Audio'}.get(kind)
        if not name:continue
        counts[kind]=counts.get(kind,0)+1
        # Ignore applies to the writer only; native reference numbering still counts it.
        if row.get('forge_include',True) is False:continue
        result.append({**{k:row.get(k) for k in ('id','name','role','description')},**cast_metadata(row),'label':f'<{name} {counts[kind]}>'})
    return result


def compile_cast_prompt(prompt, bindings, cards=None):
    from .cast_tools import cast_cards
    cards=cast_cards(cards)
    definitions=[];retention=[]
    characters=set()
    for row in bindings:
        label=row['label'];cast=row['characters'];characters.update(cast)
        if cast:
            tags=', '.join(f'<Subject {n}>' for n in cast)
            for n in cast:
                look=cards.get(str(n)) or row.get('description') or row.get('name') or 'appearance reference'
                box=next((b['box'] for b in row.get('boxes',[]) if b['n']==n),None)
                position='normalized picture box '+str(box) if box else row['position']
                definitions.append(f'<Subject {n}>: {label}; position {position}; {look}.')
            retention.append(f'{tags}: {row["retention"]}.')
        else:
            role=row.get('role') or 'reference'
            card=cards.get('pose:'+str(row['id'])) if role=='pose' else cards.get(role)
            if card or row.get('description'):definitions.append(f'{label}: {role}; {card or row["description"]}.')
    for character in characters:
        prompt=re.sub(rf'\bCharacter\s+{character}\b',f'<Subject {character}>',prompt,flags=re.IGNORECASE)
    if not definitions:return prompt
    return 'subject_definitions:\n'+'\n'.join(definitions)+'\nretention_analysis:\n'+'\n'.join(retention)+'\ndetailed_description:\n'+prompt
