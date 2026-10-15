"""Chronological predecessor frames for the dedicated prompt writer."""
from .cache_manager import ProjectCacheManager, fingerprint_value


def predecessor_context(state, clip_id, load_frames=True):
    clips=state.get('clips',[])
    index=next((i for i,c in enumerate(clips) if c.get('id')==clip_id),-1)
    if index<=0:raise ValueError('Choose a continuation clip with a previous timeline clip.')
    previous=clips[index-1]
    manager=ProjectCacheManager(state.get('project_id','default_director'))
    metadata=manager._manifest.get('clips',{}).get(previous['id'])
    if not metadata:raise ValueError('The previous clip needs a saved take for continuation drafting.')
    key=fingerprint_value(metadata)
    if not load_frames:return None,key
    frames=manager.load_clip_frames(previous['id'])
    if frames is None or frames.shape[0]<1:raise ValueError('The previous clip has no decoded frames.')
    frames=frames[-min(56,frames.shape[0]):]
    count=min(3,frames.shape[0])
    indices=list(dict.fromkeys(round(i*(frames.shape[0]-1)/max(1,count-1)) for i in range(count)))
    return frames[indices],key
