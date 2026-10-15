"""Reviewed upstream conversion with explicit compatible cache/model restoration."""
import copy,hashlib,io,json,math,uuid,zipfile
from pathlib import Path,PurePosixPath
from .task_modes import normalize_mode
from .project import migrate_timeline, seed_string
from .continuity import MODES, GRID
from .loras import normalize_loras

MEDIA={'.png','.jpg','.jpeg','.webp','.bmp','.gif','.mp4','.mov','.mkv','.webm','.wav','.mp3','.flac','.ogg','.m4a'}

def object_value(value):
    return json.loads(value) if isinstance(value,str) else value

def convert_project(data,source='auto'):
    if not isinstance(data,dict): raise ValueError('Project metadata must be an object.')
    from .foreign_review import recover_workflow,reference_metadata,reviewed_history
    data,notices=recover_workflow(data)
    warnings=list(notices)
    if source=='auto':
        source='dasiwa' if data.get('dasiwa_minimax_h3_reference_pack') else 'tritant' if 'extender' in data or isinstance(data.get('project'),dict) and 'extender' in data['project'] else 'aimixer' if 'global' in data or 'asset_groups' in data else 'current'
    signature=hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    refs=[]
    reference_ids={}
    def reference(row,kind=None):
        if row is None:return None
        if isinstance(row,dict) and isinstance(row.get('ref'),dict):row={**row,**row['ref']}
        if isinstance(row,dict) and isinstance(row.get('media'),dict):row={**row,**row['media']}
        if isinstance(row,str): row={'filename':row}
        if not isinstance(row,dict): raise ValueError('Unsupported upstream reference descriptor.')
        val=row.get('filename',row.get('value',row.get('path',row.get('file',row.get('imageFile',row.get('videoFile',row.get('audioFile',row.get('fileName'))))))))
        if isinstance(val,dict): val='/'.join(str(v) for v in (val.get('subfolder'),val.get('filename') or val.get('name')) if v)
        if not isinstance(val,str) or not val or val.startswith(('data:','http:','https:')):
            warnings.append('Skipped reference without a supported local filename.');return None
        path=PurePosixPath(val.replace('\\','/'))
        if path.is_absolute() or '..' in path.parts or ':' in val: raise ValueError('Reference paths must remain relative to input.')
        kind=kind or row.get('type') or ('image' if path.suffix.lower() in {'.png','.jpg','.jpeg','.webp','.bmp','.gif'} else 'audio' if path.suffix.lower() in {'.wav','.mp3','.flac','.ogg','.m4a'} else 'video')
        if kind not in ('image','video','audio'): warnings.append(f'Skipped unsupported reference type {kind}.');return None
        rid='import_'+uuid.uuid5(uuid.NAMESPACE_URL,signature+val+str(len(refs))).hex
        if row.get('id'): reference_ids[str(row['id'])]=rid
        refs.append({'id':rid,'type':kind,'filename':str(path),'name':row.get('name') or path.name,
            'start':row.get('start',row.get('trim_start',0)), 'end':row.get('end',row.get('trim_end')),
            'role':row.get('role',row.get('forge_role','subject')), 'description':row.get('description',row.get('forge_instructions','')),
            'media_mode':{'V':'video','A':'audio','VA':'both','V+A':'both'}.get(row.get('media_mode'),row.get('media_mode','video')),
            'scaling':'Off',**reference_metadata(row)})
        return rid
    if source=='current':
        state=copy.deepcopy(data.get('timeline',data))
        if not isinstance(state.get('clips'),list): raise ValueError('No supported clip list found.')
    elif source=='dasiwa':
        ids=[rid for row in data.get('items',[]) if (rid:=reference(row))]
        prompt=data.get('prompt',{})
        state={'clips':[{'type':data.get('model_mode','REF2VA'),'prompt':prompt.get('simple_prompt','') if isinstance(prompt,dict) else str(prompt),'duration':data.get('duration',5),'ref_ids':ids}],'references':refs}
        warnings.append('DaSiWa cast/reference metadata converted. Imported prompt history is review-only until explicitly prepared and accepted in Forge.')
    elif source=='tritant':
        project=data.get('project',data);ext=project.get('extender',{})
        settings=ext.get('settings',{})
        clip_data=object_value(ext.get('clips_json',settings.get('clips_json',{'clips':[]})))
        clips=clip_data.get('clips',[]) if isinstance(clip_data,dict) else clip_data
        mode=ext.get('generation_mode',settings.get('generation_mode','REF2VA'))
        ref_data=object_value(ext.get('refs_json',settings.get('refs_json',{'refs':ext.get('references',[])})))
        ids=[rid for row in ref_data.get('refs',[]) if (rid:=reference(row,'image'))]
        inherited={key:ext.get(key,settings.get(key)) for key in ('context_length','audio_context_length','motion_context') if key in ext or key in settings}
        state={'clips':[{**inherited,**row,'type':row.get('type',mode),'ref_ids':ids} for row in clips],'references':refs}
        for row in state['clips']:
            endpoints=[reference(row.get(key),'image') for key in ('first_frame','last_frame')]
            if str(mode).lower()=='fl2va':
                row['type']='FL2VA' if all(endpoints) else 'I2VA' if endpoints[0] else 'L2VA' if endpoints[1] else 'T2VA'
                row['ref_ids']=[rid for rid in endpoints if rid]
                if row.get('first_source')=='previous_clip':row['continuity_mode']=MODES[3]
            else:
                local=row.get('local_refs',{})
                row['ref_ids']=[*ids,*[rid for key,kind in [('images','image'),('videos','video'),('audios','audio')] for ref in local.get(key,[]) if (rid:=reference(ref,kind))]]
            if not row.get('loras') and row.get('lora'):row['loras']=[row['lora']]
            for guide in row.get('guides',[]):
                if not guide.get('ref_id'):
                    guide['ref_id']=reference(guide.get('frame',guide.get('guide_frame')),'image')
        source_video=clip_data.get('continue_existing_video') if isinstance(clip_data,dict) else None
        if source_video:
            rid=reference(source_video,'video')
            seconds=float(source_video.get('duration') or float(source_video.get('frame_count',0))/float(source_video.get('fps') or 24))
            if rid and math.isfinite(seconds) and seconds>0:
                state['clips'].insert(0,{'id':'imported_source_video','name':'Existing Video','type':'V2V','duration':seconds,'source':{'ref_id':rid},'source_start':0,'source_end':seconds,'locked':True,'audio_mode':'source','continuity':False})
            else:raise ValueError('Tritant Clip 0 needs a resolvable video and positive duration.')
        warnings.append('Recognized Tritant settings are exposed on the converted Config output. Restore Compatible Takes can import validated native H3 cache segments from project archives.')
    elif source=='aimixer':
        common=data.get('global',{})
        clips=next((data[key] for key in ('clips','segments','shots','asset_groups','groups','r2vGroups','fl2vGroups') if isinstance(data.get(key),list) and data[key]),[])
        if not isinstance(clips,list) or not clips: raise ValueError('AIMixer archive needs its timeline.json with an explicit clip/segment/group list.')
        state={'clips':[], 'references':refs,'shared_prompt':common.get('prompt','')}
        for row_index,row in enumerate(clips):
            ids=[]
            for keys,kind in [(('images','refs'),'image'),(('videos','refVideos','ref_videos'),'video'),(('audios','refAudios','ref_audios'),'audio')]:
                for ref in [r for owner in (common,row) for key in keys for r in owner.get(key,[])]:
                    rid=reference(ref,kind)
                    if rid: ids.append(rid)
            for owner in (common,row):
                legacy=owner.get('referenceVideo',owner.get('reference_video',{}))
                if legacy and not owner.get('refVideos',owner.get('ref_videos')):
                    rid=reference(legacy,'video')
                    if rid:ids.append(rid)
            inherited={key:common[key] for key in ('continuity','continuity_mode','context_length','audio_context_length') if key in common}
            kind=row.get('type',row.get('taskType') or common.get('taskType','FL2V' if 'fl2vGroups' in data else 'REF2V' if 'r2vGroups' in data else 'T2V'))
            if str(kind).lower() in ('fl2v','i2v','l2v'):
                first=reference(row.get('startImage',row.get('genImage')),'image');last=reference(row.get('endImage'),'image')
                ids=[rid for rid in (first,last) if rid];kind='FL2VA' if first and last else 'I2VA' if first else 'L2VA' if last else 'T2VA'
            row=copy.deepcopy(row)
            if normalize_mode(kind) in ('V2V','RV2V'):
                sources=data.get('videoClips',[])
                source_video=sources[row_index] if row_index<len(sources) else data.get('video')
                rid=reference(source_video,'video') if source_video else None
                if rid:
                    row['source']={'ref_id':rid}
                    row['source_start']=float(source_video.get('start',0)) if row_index<len(sources) else float(row.get('start',0))/24
                    row['source_end']=row['source_start']+float(row.get('length',row.get('frameCount',120)))/24
                else:warnings.append(f'Clip {row_index+1}: source video could not be resolved; assign it before running.')
            state['clips'].append({**inherited,**row,'type':kind,'duration':row.get('duration',row.get('duration_sec',row.get('durationSec') or float(row.get('frameCount',row.get('length',120)))/24)),'ref_ids':ids,
                **({'continuity':bool(row['continuityFromPrev'])} if 'continuityFromPrev' in row and row['continuityFromPrev'] is not None else {})})
        warnings.append('Recognized AIMixer settings are exposed on Config; explicit installed checkpoint bindings need Restore Models. Unrecognized group fields are reported for review.')
    else: raise ValueError('Unknown project format.')
    if not state.get('clips'): raise ValueError('No clips were converted.')
    original_clips=list(state['clips'])
    clips=[]
    for index,row in enumerate(state['clips']):
        if not isinstance(row,dict):raise ValueError('Imported clips must be objects.')
        kind=normalize_mode(row.get('type','T2V'));duration=float(row.get('duration',row.get('duration_sec',5)))
        if not math.isfinite(duration) or duration<=0: raise ValueError('Imported durations must be positive.')
        clip={**copy.deepcopy(row)} if source=='current' else {}
        clip.update({'id':row.get('id') if source=='current' and row.get('id') else 'clip_'+uuid.uuid5(uuid.NAMESPACE_URL,signature+str(index)).hex,'name':str(row.get('name',f'Clip {index+1}')),'type':kind,'duration':duration,
            'prompt':str(row.get('prompt','')),'seed':seed_string(row.get('seed',0)),'validated':False,'selected':False,
            'ref_ids':row.get('ref_ids',[]),'continuity_mode':'Independent (No Continuity)','context_length':22,'audio_context_length':22}
        )
        aliases={'Independent':MODES[0],'Motion Context':MODES[1],'Latent Carry':MODES[2],'FL2VA Tail Handoff':MODES[3]}
        mode=row.get('continuity_mode',row.get('continuity_method'))
        if mode is None and row.get('motion_context') is True:mode=MODES[1]
        if mode is None and row.get('continuity') is True:mode=MODES[1]
        if row.get('motion_context') is False:clip['continuity']=False
        if mode is not None:
            mode=aliases.get(mode,mode)
            if mode not in MODES: raise ValueError(f'Clip {index+1}: unsupported continuity method {mode}.')
            clip['continuity_mode']=mode
        for key in ('context_length','audio_context_length'):
            if key in row:
                value=int(row[key])
                if source=='tritant' and key=='audio_context_length' and value==0:
                    value=int(row.get('context_length',22))
                    warnings.append(f'Clip {index+1}: Tritant audio context 0 means follow video; converted to {value} frames.')
                if value not in ((*GRID,0) if key=='audio_context_length' else GRID):raise ValueError(f'Invalid {key}.')
                clip[key]=value
        for key in ('source','source_start','source_end','locked','audio_mode','color','continuity','continuity_redraw','seed_mode','tail_seconds'):
            if key in row: clip[key]=row[key]
        if source=='tritant' and isinstance(row.get('color_adjustment'),dict):
            raw=row['color_adjustment'];values={key:float(raw.get(key,100))/100 for key in ('saturation','contrast','brightness')}
            if any(not math.isfinite(v) or v<0 or v>2 for v in values.values()) or values['brightness']<=0:raise ValueError('Invalid imported Tritant color adjustment.')
            clip['color']={'exposure':math.log2(values['brightness']),'contrast':values['contrast'],'saturation':values['saturation'],'model':'css'}
        if source!='current' and isinstance(clip.get('source'),dict) and clip['source'].get('ref_id'):
            clip['source']={**clip['source'],'ref_id':reference_ids.get(str(clip['source']['ref_id']),clip['source']['ref_id'])}
        if source!='current':
            if 'loras' in row:
                if not isinstance(row['loras'],list) or any(not isinstance(a,dict) for a in row['loras']):raise ValueError('Imported LoRAs must be a list of objects.')
                adapters=[{'name':a.get('name',a.get('lora_name','')),'strength':float(a.get('strength',a.get('strength_model',1))),**({'enabled':False} if a.get('enabled',a.get('active',True)) is False else {})} for a in row['loras']]
                normalize_loras([{**a,'enabled':True} for a in adapters])
                clip['loras']=adapters
                warnings.append(f'Clip {index+1}: LoRA names/strengths converted; installed model compatibility must be checked.')
            if 'guides' in row:
                clip['guides']=[]
                for guide in row['guides']:
                    rid=reference_ids.get(str(guide.get('ref_id')),guide.get('ref_id'))
                    if rid not in {r['id'] for r in refs}:
                        warnings.append(f'Clip {index+1}: omitted guide with unresolved reference {guide.get("ref_id")}.');continue
                    frame_idx=float(guide.get('frame_idx',0))
                    if frame_idx<0:
                        from .config import align_frame_count
                        frame_idx=align_frame_count(round(duration*24))+frame_idx
                    time=float(guide.get('time',frame_idx/24))
                    if not math.isfinite(time) or not 0<=time<duration:raise ValueError('Imported guide time is outside the clip.')
                    clip['guides'].append({'ref_id':rid,'time':time})
            if any(key in row for key in ('refmod','refmods','model','model_override')):
                warnings.append(f'Clip {index+1}: review RefMod/model bindings on the converted dedicated outputs; unnamed runtime objects cannot be restored.')
        clips.append(clip)
    state.update(version=2,approval_control_version=1,project_id=state.get('project_id') if source=='current' and state.get('project_id') else 'project_'+signature[:24],clips=clips)
    state=migrate_timeline(state)
    from .cast_tools import cast_cards
    if source!='current':
        state['cast_cards']=cast_cards(data.get('cast_cards'))
        state['imported_prompt_history']=reviewed_history(data)
    from .import_bindings import converted_bindings
    bindings=converted_bindings(data,source)
    if source!='current':
        state['import_bindings']=bindings
        state['source_clip_ids']={str(old['id']):new['id'] for old,new in zip(original_clips,state['clips']) if old.get('id')}
        if bindings['refmods']:state['refmods']=[{**r,'slot':i+1} for i,r in enumerate(bindings['refmods'])]
        for old,new in zip(original_clips,state['clips']):
            if old.get('model_override') in bindings['model_bindings']:new['model_override']=old['model_override']
    elif state.get('imported_take_ids'):
        from .cache_manager import ProjectCacheManager
        manager=ProjectCacheManager(state['project_id'])
        previous={r.get('id'):r for r in original_clips}
        for clip in state['clips']:
            meta=manager._manifest.get('clips',{}).get(clip['id'],{})
            if clip['id'] in state['imported_take_ids'] and meta.get('imported_from')=='tritant' and meta.get('has_latent'):
                clip['validated']=bool(previous[clip['id']].get('validated'))
    return state,{'source':source,'clips':len(clips),'references':len(state.get('references',[])),'warnings':warnings,'cache_imported':False,
        'bindings':bindings,'history_entries':len(state.get('imported_prompt_history',[])),'cast_cards':len(state.get('cast_cards',{})),
        'preserved_fields':['prompt','duration','seed','continuity','context_length','audio_context_length','source','audio_mode','color','LoRA names/strengths','resolved guide times'],
        'not_imported':['unnamed runtime checkpoint objects','procedural graph patches and unavailable source artifacts'] if source!='current' else ['take artifacts; existing project cache is referenced by project ID']}

def read_conversion(blob,input_root,source='auto',restore_cache=False,cache_root=None,progress=None):
    progress=progress or (lambda *args:None)
    root=Path(input_root).resolve();files={}
    is_bytes=isinstance(blob,(bytes,bytearray))
    archive_source=io.BytesIO(blob) if is_bytes else str(blob)
    if zipfile.is_zipfile(archive_source):
        with zipfile.ZipFile(archive_source) as archive:
            entries=archive.infolist()
            if len(entries)>5000 or sum(e.file_size for e in entries)>8*1024**3: raise ValueError('Project archive is too large.')
            if len({e.filename for e in entries})!=len(entries):raise ValueError('Duplicate archive entries are not supported.')
            for entry in entries:
                if (entry.external_attr >> 16) & 0o170000 == 0o120000:raise ValueError('Archive links are not supported.')
                path=PurePosixPath(entry.filename)
                if path.is_absolute() or '..' in path.parts or ':' in entry.filename or '\\' in entry.filename: raise ValueError('Unsafe archive path.')
            name='timeline.json' if 'timeline.json' in archive.namelist() else 'project.json' if 'project.json' in archive.namelist() else 'pack.json'
            if name not in archive.namelist(): raise ValueError('Archive has no supported project metadata.')
            if archive.getinfo(name).file_size>16*1024**2: raise ValueError('Project JSON is too large.')
            data=json.loads(archive.read(name))
            from .foreign_archives import archive_metadata
            data=archive_metadata(archive,data,name)
            if name=='timeline.json' and source=='auto':source='aimixer'
            state,report=convert_project(data,source)
            if is_bytes:digest=hashlib.sha256(blob).hexdigest()
            else:
                with open(blob,'rb') as raw:digest=hashlib.file_digest(raw,'sha256').hexdigest()
            if report['source']!='current':state['project_id']='project_'+digest[:24]
            prefix=PurePosixPath('minimax_imports')/digest[:24]
            for entry in entries:
                if (PurePosixPath(entry.filename).suffix.lower() in MEDIA or entry.filename in {r.get('filename') for r in state.get('references',[])}) and not entry.is_dir():files[entry.filename]=(str(prefix/entry.filename),entry)
            # Conversion and all path checks finish before writing any asset.
            from .transfer import copy_progress
            total=sum(entry.file_size for _,entry in files.values());done=0
            for original,(relative,entry) in files.items():
                target=(root/relative).resolve()
                if not target.is_relative_to(root):raise ValueError('Archive asset escaped input directory.')
                target.parent.mkdir(parents=True,exist_ok=True)
                with archive.open(entry) as src,target.open('wb') as dest:
                    done+=copy_progress(src,dest,progress,"Extracting media",done,total)
            for row in state.get('references',[]):
                if row['filename'] in files:row['filename']=files[row['filename']][0]
            report['embedded_media']=len(files)
            if restore_cache and report['source']=='tritant':
                from .foreign_cache import import_tritant_cache
                report['restored_takes']=import_tritant_cache(archive,state,cache_root,digest,progress)
                report['cache_imported']=bool(report['restored_takes'])
                state['imported_take_ids']=report['restored_takes']
                if report['cache_imported']:report['warnings'].append('Compatible H3 latents restored. Run Master once to decode saved takes using your connected H3 VAEs; no sampling is needed for restored approved clips.')
    else:
        if not is_bytes:
            if Path(blob).stat().st_size>16*1024**2:raise ValueError('Project JSON is too large.')
            blob=Path(blob).read_bytes()
        if len(blob)>16*1024**2: raise ValueError('Project JSON is too large.')
        state,report=convert_project(json.loads(blob),source)
    missing=[row['filename'] for row in state.get('references',[]) if not (root/row['filename']).is_file()]
    progress('Conversion complete',1,1)
    report['missing_files']=missing
    return state,report
