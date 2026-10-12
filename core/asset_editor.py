"""Non-destructive pack-owned media preparation with stable reference IDs."""
import json, math
from .references import edit_images, load_reference, ROLES
from .media_io import scale_tensor_image


def prepare_asset(row, settings):
    if not settings: return row
    row={**row}
    role=settings.get('role','subject')
    if role not in ROLES: raise ValueError('Unknown reference role.')
    row.update(role=role,description=str(settings.get('description','')))
    if 'name' in settings: row['name']=str(settings['name']).strip() or row.get('slot_id',row['id'])
    kind=row['type'];data=row.get('data')
    if kind=='refmod': return row
    start=float(settings.get('start',0));end=settings.get('end')
    end=float(end) if end not in (None,'') else None
    if not math.isfinite(start) or start<0 or end is not None and (not math.isfinite(end) or end<=start):
        raise ValueError('Reference trim must have a non-negative start and later end.')
    if kind in ('audio','video'):
        rate=24 if kind=='video' else int(data['sample_rate'])
        count=data.shape[0] if kind=='video' else data['waveform'].shape[-1]
        lo=round(start*rate);hi=min(count,round(end*rate)) if end is not None else count
        if lo>=hi: raise ValueError('Reference trim is outside the available media.')
        if kind=='video':
            data=data[lo:hi]
            if row.get('audio'):
                audio=row['audio'];ar=int(audio['sample_rate'])
                row['audio']={**audio,'waveform':audio['waveform'][...,round(lo/24*ar):round(hi/24*ar)]}
        else: data={**data,'waveform':data['waveform'][...,lo:hi]}
    if kind=='video':
        mode=settings.get('media_mode','both')
        if mode not in ('video','audio','both','frame'): raise ValueError('Unknown video presentation.')
        if mode=='audio':
            if not row.get('audio'): raise ValueError('Audio-only video needs a connected soundtrack.')
            row.update(type='audio',data=row['audio']);row.pop('audio',None)
            return row
        if mode=='video': row.pop('audio',None)
        if mode=='frame':
            time=float(settings.get('frame_time',0))
            index=round(time*24)
            if not math.isfinite(time) or index<0 or index>=data.shape[0]: raise ValueError('Frame pick is outside the trimmed video.')
            data=data[index:index+1];row['type']='image';row.pop('audio',None)
    if row['type'] in ('image','video'):
        data=edit_images(data,settings.get('edits'),settings.get('crop'))
        scaling=settings.get('scaling','Off')
        data=scale_tensor_image(data,scaling,int(settings.get('width',1344)),int(settings.get('height',768)))
    row['data']=data
    return row


def prepare_pack(refs, asset_edits, input_root=None):
    settings=json.loads(asset_edits or '{}') if isinstance(asset_edits,str) else asset_edits
    if not isinstance(settings,dict): raise ValueError('Asset editor state must be an object.')
    assets=settings.get('assets',{})
    if not isinstance(assets,dict): raise ValueError('Asset edits must be keyed by slot ID.')
    prepared=[prepare_asset(row,assets.get(row.get('slot_id',row['id']),{})) for row in refs]
    for row in settings.get('files',[]):
        if not input_root: raise ValueError('File assets require the ComfyUI input directory.')
        row={**row,'scaling':row.get('scaling','Off')}
        frame_pick=row.get('type')=='video' and row.get('media_mode')=='frame'
        loaded=load_reference({**row,'media_mode':'both'} if frame_pick else row,input_root,int(row.get('width',1344)),int(row.get('height',768)))
        # Video+audio is one paired reference, not two ambiguous selections.
        paired=next((item for item in loaded if item.get('paired_video_id')),None)
        visual=next((item for item in loaded if item['type']=='video'),None)
        if paired and visual:
            visual['audio']=paired['data'];loaded=[visual]
        if frame_pick:
            if visual is None: raise ValueError('Frame picking needs video pixels.')
            seconds=float(row.get('frame_time',0))
            if not math.isfinite(seconds) or seconds<0 or round(seconds*24)>=visual['data'].shape[0]: raise ValueError('Frame pick is outside the trimmed video.')
            index=round(seconds*24)
            visual={**visual,'type':'image','data':visual['data'][index:index+1]}
            visual.pop('audio',None);loaded=[visual]
        if row.get('type')=='video' and row.get('media_mode')=='audio':
            loaded=[{**item,'id':row['id']} for item in loaded]
        prepared.extend(loaded)
    ids=[row['id'] for row in prepared]
    if len(set(ids))!=len(ids): raise ValueError('Reference IDs must be unique.')
    return prepared
