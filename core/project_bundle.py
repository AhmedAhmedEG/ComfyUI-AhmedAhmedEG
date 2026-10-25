"""Stream optional input media and generated results without loading tensors."""
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import uuid
import zipfile

from .project import asset_fields, read_portable
from .project_json import prepare_workflow
from .media_io import resolve_input_path
from .transfer import copy_progress


def media_owners(document):
    yield from asset_fields(document['timeline'])
    for row in document.get('reference_catalog',[]):
        if row.get('filename'):yield row,'filename'
    for node in (document.get('workflow') or {}).get('nodes',[]):
        field={'LoadImage':'image','LoadVideo':'file','LoadAudio':'audio'}.get(node.get('type'))
        if not field:continue
        named=node.get('widgets_values_named',{})
        if named.get(field):yield named,field
        values=node.get('widgets_values',[])
        if values and isinstance(values[0],str):yield values,0


def write_bundle(manager, timeline, workflow, master_id, input_root, destination, *,
                 include_media=False, include_results=False, progress=None):
    progress=progress or (lambda *args:None)
    document=manager.export_lightweight_project_data(timeline,workflow=workflow,master_node_id=master_id)
    files={};mapped={}
    if include_media:
        for owner,key in media_owners(document):
            filename=owner[key]
            if filename not in mapped:
                path=Path(resolve_input_path(filename,input_root))
                with path.open('rb') as source:digest=hashlib.file_digest(source,'sha256').hexdigest()
                mapped[filename]='assets/'+digest+path.suffix.lower();files[mapped[filename]]=path
            owner[key]=mapped[filename]
    results={}
    if include_results:
        for clip in document['timeline']['clips']:
            cid=clip.get('id');meta=manager._manifest.get('clips',{}).get(cid)
            if not meta:continue
            entries=[]
            for name in sorted(manager._result_files(cid,meta)):
                if Path(name).name!=name:raise ValueError('Unsafe generated-result filename.')
                path=Path(manager.project_dir)/name
                if path.is_symlink():raise ValueError('Generated result must not be a symbolic link.')
                if path.is_file():
                    entry='results/'+name;files[entry]=path;entries.append(entry)
            if entries:results[cid]={'metadata':meta,'files':entries}
    payload={'format':'MiniMaxH3ProjectBundle','version':1,'project':document,'results':results}
    total=sum(p.stat().st_size for p in files.values());done=0
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED,allowZip64=True) as archive:
        archive.writestr('project.json',json.dumps(payload,ensure_ascii=False))
        for entry,path in files.items():
            with path.open('rb') as source,archive.open(entry,'w',force_zip64=True) as target:
                done+=copy_progress(source,target,progress,'Packing project',done,total)
    progress('Packing project',total,total)
    return destination


def read_bundle(source,input_root,*,max_bytes=256*1024**3,progress=None):
    from .cache_manager import ProjectCacheManager,safe_component
    progress=progress or (lambda *args:None)
    with zipfile.ZipFile(source) as archive:
        infos=archive.infolist();names=set()
        if len(infos)>10000 or sum(i.file_size for i in infos)>max_bytes:raise ValueError('Project archive exceeds import limits.')
        for info in infos:
            name=PurePosixPath(info.filename)
            if (name.is_absolute() or '..' in name.parts or '\\' in info.filename or ':' in info.filename
                    or info.filename in names or (info.external_attr>>16)&0o170000==0o120000):
                raise ValueError('Unsafe or duplicate project archive path.')
            names.add(info.filename)
        if 'project.json' not in names or archive.getinfo('project.json').file_size>16*1024**2:
            raise ValueError('Archive has no valid project manifest.')
        payload=json.loads(archive.read('project.json'))
        if payload.get('format')=='MiniMaxH3Portable':
            return {'timeline':read_portable(source,input_root,max_bytes=max_bytes,progress=progress),'workflow':None}
        if payload.get('format')!='MiniMaxH3ProjectBundle' or payload.get('version')!=1:raise ValueError('Unsupported project archive.')
        document=copy.deepcopy(payload['project']);results=payload.get('results',{})
        # Bundled results always enter a new project: never overwrite existing takes.
        if results:document['project_id']='import_'+uuid.uuid4().hex
        manager=ProjectCacheManager(document['project_id'])
        owners=list(media_owners(document));assets={owner[key] for owner,key in owners if str(owner[key]).startswith('assets/')}
        for name in assets:
            if name not in names or len(PurePosixPath(name).parts)!=2:raise ValueError('Missing bundled input asset.')
        result_files={}
        for cid,row in results.items():
            safe_component(cid);meta=row['metadata'];safe_component(meta['generation'])
            allowed=manager._result_files(cid,meta)
            for name in row['files']:
                if name not in names or PurePosixPath(name).parts!=('results',PurePosixPath(name).name) or PurePosixPath(name).name not in allowed:
                    raise ValueError('Unsafe or missing generated-result entry.')
                result_files[name]=PurePosixPath(name).name
        # Validate authoring IDs and workflow before writing any imported artifacts.
        timeline=manager.import_lightweight_project_data(document)
        for original,normalized in zip(document['timeline']['clips'],timeline['clips']):original['id']=normalized['id']
        if document.get('workflow') is not None:prepare_workflow(document['workflow'],document.get('master_node_id'),timeline)
        folder='minimax_imports/'+uuid.uuid4().hex
        total=sum(archive.getinfo(name).file_size for name in assets|set(result_files));done=0
        with tempfile.TemporaryDirectory(prefix='minimax_bundle_') as temp:
            staged=Path(temp)
            for name in sorted(assets|set(result_files)):
                target=staged/name;target.parent.mkdir(parents=True,exist_ok=True)
                with archive.open(name) as source_file,target.open('wb') as target_file:
                    done+=copy_progress(source_file,target_file,progress,'Importing project',done,total)
            for name in assets:
                target=Path(input_root)/folder/PurePosixPath(name).name;target.parent.mkdir(parents=True,exist_ok=True)
                shutil.move(str(staged/name),str(target))
            for name,filename in result_files.items():shutil.move(str(staged/name),str(Path(manager.project_dir)/filename))
        for owner,key in owners:
            if owner[key] in assets:owner[key]=folder+'/'+PurePosixPath(owner[key]).name
        if results:
            manager._manifest['clips']={cid:row['metadata'] for cid,row in results.items()};manager.save_manifest()
        timeline=manager.import_lightweight_project_data(document)
        workflow=prepare_workflow(document['workflow'],document.get('master_node_id'),timeline) if document.get('workflow') is not None else None
        return {'timeline':timeline,'workflow':workflow,'restored_results':len(results),'project':document}
