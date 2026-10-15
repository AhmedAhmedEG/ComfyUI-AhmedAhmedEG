"""Translate recognized source settings into existing configuration contracts."""
import math,os


def converted_bindings(data,source):
    if source=='tritant':
        ext=data.get('project',data).get('extender',{});settings={**ext.get('settings',{}),**ext}
    elif source=='aimixer':settings={**data.get('global',{}),**data.get('widgets',{})}
    else:settings=data.get('settings',data.get('config',{}))
    config={}
    numeric={'width':(int,32,16384),'height':(int,32,16384),'steps':(int,1,200),'cfg':(float,0,20),'shift_video':(float,.1,100),'shift_audio':(float,.1,100)}
    for key,(cast,low,high) in numeric.items():
        if key not in settings:continue
        value=cast(settings[key])
        if not math.isfinite(value) or not low<=value<=high:raise ValueError(f'Invalid imported {key}.')
        if key in ('width','height') and value%32:raise ValueError('Imported H3 canvas must be divisible by 32.')
        config[key]=value
    for key in ('sampler','scheduler'):
        if key in settings:config[key]=str(settings[key])
    if 'width' in config and 'height' in config:config['resolution']={'mode':'manual','width':config['width'],'height':config['height']}
    # Native H3 owns generation FPS; output playback remains an output-node policy.
    config['frame_rate']=24.
    models={}
    for alias,value in (data.get('model_bindings') or settings.get('model_bindings') or {}).items():
        if not isinstance(value,dict) or value.get('category','diffusion_models')!='diffusion_models':raise ValueError('Imported model bindings need explicit diffusion-model filenames.')
        name=value.get('filename','')
        if not name or os.path.isabs(name) or '..' in name.replace('\\','/').split('/'):raise ValueError('Imported model filenames must be relative.')
        models[str(alias)]={'filename':name,'weight_dtype':value.get('weight_dtype','default')}
    mods=data.get('refmods',settings.get('refmods',[])) or []
    if not isinstance(mods,list):raise ValueError('Imported RefMods must be a list.')
    canonical=[]
    for index,row in enumerate(mods):
        if isinstance(row,str):row={'name':row}
        name=str(row.get('name',row.get('filename','')))
        if not name:continue
        strength=float(row.get('strength',1))
        if not math.isfinite(strength) or not 0<=strength<=4:raise ValueError('Invalid imported RefMod strength.')
        canonical.append({'id':str(row.get('id',f'import_mod_{index+1}')),'name':name,'description':row.get('description',''),'strength':strength,'enabled':row.get('enabled',True)})
    return {'config':config,'model_bindings':models,'refmods':canonical}


def load_model_bindings(bindings):
    import folder_paths
    from nodes import UNETLoader
    from .sampling import native_outputs
    result={}
    installed=folder_paths.get_filename_list('diffusion_models')
    for alias,row in bindings.items():
        name=row['filename']
        matches=[n for n in installed if n==name] or [n for n in installed if n.replace('\\','/').split('/')[-1]==name.replace('\\','/').split('/')[-1]]
        if len(matches)!=1:raise ValueError(f'Imported checkpoint is missing or ambiguous: {name}.')
        result[alias]=native_outputs(UNETLoader().load_unet(matches[0],row.get('weight_dtype','default')))[0]
    return result
