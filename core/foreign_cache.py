"""Convert known raw H3 disk segments without executing foreign pickle objects."""
import json,math,hashlib
from pathlib import Path
import numpy as np
import torch
from .cache_manager import ProjectCacheManager


def validate_tensor(path,spec):
    shape=tuple(int(v) for v in spec['shape']);offset=int(spec['offset']);count=int(spec['nbytes'])
    allowed={'float32':torch.float32,'float16':torch.float16,'bfloat16':torch.bfloat16}
    dtype=allowed.get(spec.get('dtype'))
    if dtype is None or not 1<=len(shape)<=5 or any(v<1 for v in shape):raise ValueError('Unsupported foreign H3 tensor shape/dtype.')
    expected=math.prod(shape)*torch.empty((),dtype=dtype).element_size()
    if count!=expected or count>3*1024**3 or offset<0 or offset+count>Path(path).stat().st_size:raise ValueError('Foreign latent tensor points outside its archive data.')
    return shape,offset,count,dtype


def raw_tensor(path,spec):
    shape,offset,count,dtype=validate_tensor(path,spec)
    data=np.memmap(str(path),dtype=np.uint8,mode='c',offset=offset,shape=(count,))
    return torch.from_numpy(data).view(dtype).reshape(shape),data


def import_tritant_cache(archive,state,cache_root=None,archive_digest=''):
    required={'cache/chain.json','cache/chain.h3cache'}
    if not required.issubset(archive.namelist()):return []
    if archive.getinfo('cache/chain.json').file_size>16*1024**2:raise ValueError('Foreign cache manifest is too large.')
    manifest=json.loads(archive.read('cache/chain.json'));segments=manifest.get('segments',[])
    clips=[row for row in state['clips'] if not row.get('locked')]
    if len(segments)>len(clips):raise ValueError('Foreign cache contains more segments than its timeline.')
    manager=ProjectCacheManager(state['project_id'],cache_root)
    import tempfile,shutil
    restored=[]
    with tempfile.TemporaryDirectory(dir=manager.project_dir) as root:
        path=Path(root)/'chain.raw'
        with archive.open('cache/chain.h3cache') as source,path.open('wb') as dest:shutil.copyfileobj(source,dest,1024**2)
        # Validate every descriptor before committing any take.
        rows=[]
        used=set()
        for index,segment in enumerate(segments):
            source_id=segment.get('clip_id') or (manifest.get('extender_clip_ids',[])[index] if index<len(manifest.get('extender_clip_ids',[])) else None)
            cid=state.get('source_clip_ids',{}).get(str(source_id)) if source_id is not None else clips[index]['id']
            if cid is None or cid in used:raise ValueError('Foreign cache has an unknown or duplicate clip identity.')
            used.add(cid)
            video=validate_tensor(path,segment['video'])[0];audio=validate_tensor(path,segment['audio'])[0]
            if len(video)==4:video=(1,*video)
            if len(audio)==3:audio=(1,*audio)
            if len(video)!=5 or video[:2]!=(1,24) or len(audio)!=4 or audio[:3]!=(1,32,2):raise ValueError('Foreign cache is not a native H3 audiovisual latent.')
            if video[2]<2 or (video[2]-2)%5 or min(video[3:])<2 or any(n%2 for n in video[3:]):raise ValueError('Foreign video latent violates the H3 frame/canvas grid.')
            frames=((video[2]-2)//5)*17+5
            if not 0<=int(segment.get('trim_frames',0))<frames:raise ValueError('Foreign cache trim is outside the saved take.')
            rows.append((cid,segment))
        for cid,segment in rows:
            video,vm=raw_tensor(path,segment['video']);audio,am=raw_tensor(path,segment['audio'])
            try:
                if video.ndim==4:video=video.unsqueeze(0)
                if audio.ndim==3:audio=audio.unsqueeze(0)
                clip=next(row for row in clips if row['id']==cid);fingerprint=hashlib.sha256((archive_digest+json.dumps(segment,sort_keys=True)).encode()).hexdigest()
                latent={'samples':(video,audio)}
                manager.store_clip_results(clip['id'],fingerprint,latent,validated=bool(segment.get('validated')))
                manager.update_clip_metadata(clip['id'],{'trim_prefix':int(segment.get('trim_frames',0)),'previous_trim':0,'imported_from':'tritant','mode':clip['type']})
                clip['validated']=bool(segment.get('validated'));restored.append(clip['id'])
            finally:
                latent=None
                del video,audio
                vm._mmap.close();am._mmap.close()
    return restored
