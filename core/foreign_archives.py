"""Resolve source archive slots to their embedded media before conversion."""
import copy,json


def archive_metadata(archive,data,name):
    data=copy.deepcopy(data);names=set(archive.namelist())
    def read(path,default):
        if path not in names:return default
        if archive.getinfo(path).file_size>16*1024**2:raise ValueError('Foreign JSON metadata is too large.')
        return json.loads(archive.read(path))
    if name in ('timeline.json','pack.json') and ('shared_params/shared_params.json' in names or 'taskType' in data):
        pack=read('pack.json',{});shared=read('shared_params/shared_params.json',{})
        if name=='pack.json':
            groups=[read(path,{}) for path in sorted(names) if path.startswith('asset_groups/') and path.endswith('/group.json')]
            data={'global':{**shared,'taskType':pack.get('taskType','t2v')},'segments':groups}
        data['widgets']={**pack.get('widgets',{}),**data.get('widgets',{})}
        data['global']={**shared,**data.get('global',{})}
    project=data.get('project',data);ext=project.get('extender')
    if not isinstance(ext,dict):return data
    settings=ext.get('settings',{})
    refs=ext.get('refs_json',settings.get('refs_json',{'refs':ext.get('references',[])}))
    refs=json.loads(refs) if isinstance(refs,str) else refs
    def bind(row,path,kind):
        if isinstance(row,dict) and path in names:row.update(filename=path,type=kind)
        return row
    for i,row in enumerate(refs.get('refs',[]),1):bind(row,f'refs/ref_{i}.png','image')
    ext['refs_json']=refs
    clips=ext.get('clips_json',settings.get('clips_json',{'clips':[]}))
    clips=json.loads(clips) if isinstance(clips,str) else clips
    if isinstance(clips,dict) and isinstance(clips.get('continue_existing_video'),dict):
        source=clips['continue_existing_video'];bind(source,f'local_refs/media/{source.get("id")}.bin','video')
    for i,row in enumerate(clips.get('clips',[]) if isinstance(clips,dict) else clips,1):
        for key,kind in [('first_frame','first'),('last_frame','last')]:bind(row.get(key),f'fl2va/clip_{i}_{kind}.png','image')
        for j,guide in enumerate(row.get('guides',[]),1):bind(guide.get('frame'),f'fl2va/clip_{i}_guide_{j}.png','image')
        local=row.get('local_refs',{})
        for item in local.get('images',[]):
            ref=item.get('ref',item);bind(ref,f'local_refs/images/{ref.get("id")}.png','image')
        for key,kind in [('videos','video'),('audios','audio')]:
            for item in local.get(key,[]):
                ref=item.get('media',item);bind(ref,f'local_refs/media/{ref.get("id")}.bin',kind)
    ext['clips_json']=clips
    return data
