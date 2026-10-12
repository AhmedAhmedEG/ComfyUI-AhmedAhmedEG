"""Explicit upstream authoring conversion; caches/weights are never executed."""
import copy,hashlib,io,json,math,uuid,zipfile
from pathlib import Path,PurePosixPath
from .task_modes import normalize_mode

MEDIA={'.png','.jpg','.jpeg','.webp','.bmp','.gif','.mp4','.mov','.mkv','.webm','.wav','.mp3','.flac','.ogg','.m4a'}

def object_value(value):
    return json.loads(value) if isinstance(value,str) else value

def convert_project(data,source='auto'):
    if not isinstance(data,dict): raise ValueError('Project metadata must be an object.')
    warnings=[]
    if source=='auto':
        source='dasiwa' if data.get('dasiwa_minimax_h3_reference_pack') else 'tritant' if 'extender' in data or isinstance(data.get('project'),dict) and 'extender' in data['project'] else 'aimixer' if 'global' in data or 'asset_groups' in data else 'current'
    signature=hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    refs=[]
    def reference(row,kind=None):
        if isinstance(row,str): row={'filename':row}
        if not isinstance(row,dict): raise ValueError('Unsupported upstream reference descriptor.')
        val=row.get('filename',row.get('value',row.get('path',row.get('file'))))
        if isinstance(val,dict): val='/'.join(str(v) for v in (val.get('subfolder'),val.get('filename') or val.get('name')) if v)
        if not isinstance(val,str) or not val or val.startswith(('data:','http:','https:')):
            warnings.append('Skipped reference without a supported local filename.');return None
        path=PurePosixPath(val.replace('\\','/'))
        if path.is_absolute() or '..' in path.parts or ':' in val: raise ValueError('Reference paths must remain relative to input.')
        kind=kind or row.get('type') or ('image' if path.suffix.lower() in {'.png','.jpg','.jpeg','.webp','.bmp','.gif'} else 'audio' if path.suffix.lower() in {'.wav','.mp3','.flac','.ogg','.m4a'} else 'video')
        if kind not in ('image','video','audio'): warnings.append(f'Skipped unsupported reference type {kind}.');return None
        rid='import_'+uuid.uuid5(uuid.NAMESPACE_URL,signature+val+str(len(refs))).hex
        refs.append({'id':rid,'type':kind,'filename':str(path),'name':row.get('name') or path.name,
            'start':row.get('start',row.get('trim_start',0)), 'end':row.get('end',row.get('trim_end')),
            'role':row.get('role',row.get('forge_role','subject')), 'description':row.get('description',row.get('forge_instructions','')),
            'media_mode':{'V':'video','A':'audio','VA':'both','V+A':'both'}.get(row.get('media_mode'),row.get('media_mode','video')),
            'scaling':'Off'})
        return rid
    if source=='current':
        state=copy.deepcopy(data.get('timeline',data))
        if not isinstance(state.get('clips'),list): raise ValueError('No supported clip list found.')
    elif source=='dasiwa':
        ids=[rid for row in data.get('items',[]) if (rid:=reference(row))]
        prompt=data.get('prompt',{})
        state={'clips':[{'type':data.get('model_mode','REF2VA'),'prompt':prompt.get('simple_prompt','') if isinstance(prompt,dict) else str(prompt),'duration':data.get('duration',5),'ref_ids':ids}],'references':refs}
        warnings.append('DaSiWa prompt mapping/Forge history and RefMod bundles require review in the dedicated nodes.')
    elif source=='tritant':
        project=data.get('project',data);ext=project.get('extender',{})
        settings=ext.get('settings',{})
        clip_data=object_value(ext.get('clips_json',settings.get('clips_json',{'clips':[]})))
        clips=clip_data.get('clips',[]) if isinstance(clip_data,dict) else clip_data
        mode=ext.get('generation_mode',settings.get('generation_mode','REF2VA'))
        ref_data=object_value(ext.get('refs_json',{'refs':ext.get('references',[])}))
        ids=[rid for row in ref_data.get('refs',[]) if (rid:=reference(row))]
        state={'clips':[{**row,'type':row.get('type',mode),'ref_ids':ids} for row in clips],'references':refs}
        warnings.append('Tritant caches, latent approvals and model settings are not imported. Configure Settings and regenerate or import decoded footage.')
    elif source=='aimixer':
        common=data.get('global',{})
        clips=next((data[key] for key in ('clips','segments','shots','asset_groups','groups','r2vGroups','fl2vGroups') if isinstance(data.get(key),list) and data[key]),[])
        if not isinstance(clips,list) or not clips: raise ValueError('AIMixer archive needs its timeline.json with an explicit clip/segment/group list.')
        state={'clips':[], 'references':refs,'shared_prompt':common.get('prompt','')}
        for row in clips:
            ids=[]
            for key,kind in [('images','image'),('videos','video'),('audios','audio')]:
                for ref in [*common.get(key,[]),*row.get(key,[])]:
                    rid=reference(ref,kind)
                    if rid: ids.append(rid)
            state['clips'].append({**row,'type':row.get('type',row.get('taskType',common.get('taskType','FL2V' if 'fl2vGroups' in data else 'REF2V' if 'r2vGroups' in data else 'T2V'))),'duration':row.get('duration',row.get('duration_sec',5)),'ref_ids':ids})
        warnings.append('AIMixer sampler/model settings, output cache and unrecognized group fields are not automatically applied.')
    else: raise ValueError('Unknown project format.')
    if not state.get('clips'): raise ValueError('No clips were converted.')
    clips=[]
    for index,row in enumerate(state['clips']):
        kind=normalize_mode(row.get('type','T2V'));duration=float(row.get('duration',row.get('duration_sec',5)))
        if not math.isfinite(duration) or duration<=0: raise ValueError('Imported durations must be positive.')
        clip={'id':row.get('id') if source=='current' and row.get('id') else 'clip_'+uuid.uuid5(uuid.NAMESPACE_URL,signature+str(index)).hex,'name':str(row.get('name',f'Clip {index+1}')),'type':kind,'duration':duration,
            'prompt':str(row.get('prompt','')),'seed':str(row.get('seed',0)),'validated':False,'selected':False,
            'ref_ids':row.get('ref_ids',[]),'continuity_mode':'Independent (No Continuity)','context_length':22,'audio_context_length':22}
        for key in ('source','source_start','source_end','locked','audio_mode','color'):
            if key in row: clip[key]=row[key]
        if source=='current':
            for key in ('guides','loras'):
                if key in row:clip[key]=row[key]
        if source!='current' and any(key in row for key in ('guides','loras','refmod','refmods')):
            warnings.append(f'Clip {index+1}: review guide/LoRA/RefMod settings in their dedicated nodes; foreign model bindings were omitted.')
        clips.append(clip)
    state.update(version=2,approval_control_version=1,project_id=state.get('project_id') if source=='current' and state.get('project_id') else 'project_'+signature[:24],clips=clips)
    return state,{'source':source,'clips':len(clips),'references':len(state.get('references',[])),'warnings':warnings,'cache_imported':False}

def read_conversion(blob,input_root,source='auto'):
    root=Path(input_root).resolve();files={}
    if zipfile.is_zipfile(io.BytesIO(blob)):
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            entries=archive.infolist()
            if len(entries)>5000 or sum(e.file_size for e in entries)>8*1024**3: raise ValueError('Project archive is too large.')
            for entry in entries:
                path=PurePosixPath(entry.filename)
                if path.is_absolute() or '..' in path.parts or ':' in entry.filename or '\\' in entry.filename: raise ValueError('Unsafe archive path.')
            name='timeline.json' if 'timeline.json' in archive.namelist() else 'project.json' if 'project.json' in archive.namelist() else 'pack.json'
            if name not in archive.namelist(): raise ValueError('Archive has no supported project metadata.')
            if archive.getinfo(name).file_size>16*1024**2: raise ValueError('Project JSON is too large.')
            data=json.loads(archive.read(name))
            if name=='timeline.json' and source=='auto':source='aimixer'
            state,report=convert_project(data,source)
            prefix=PurePosixPath('minimax_imports')/hashlib.sha256(blob).hexdigest()[:24]
            for entry in entries:
                if PurePosixPath(entry.filename).suffix.lower() in MEDIA and not entry.is_dir():files[entry.filename]=(str(prefix/entry.filename),entry)
            # Conversion and all path checks finish before writing any asset.
            for original,(relative,entry) in files.items():
                target=(root/relative).resolve()
                if not target.is_relative_to(root):raise ValueError('Archive asset escaped input directory.')
                target.parent.mkdir(parents=True,exist_ok=True)
                with archive.open(entry) as src,target.open('wb') as dest:
                    import shutil
                    shutil.copyfileobj(src,dest,1024**2)
            for row in state.get('references',[]):
                if row['filename'] in files:row['filename']=files[row['filename']][0]
            report['embedded_media']=len(files)
    else:
        if len(blob)>16*1024**2: raise ValueError('Project JSON is too large.')
        state,report=convert_project(json.loads(blob),source)
    missing=[row['filename'] for row in state.get('references',[]) if not (root/row['filename']).is_file()]
    report['missing_files']=missing
    return state,report
