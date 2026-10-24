"""Materialize the selected preview as IMAGE/AUDIO only for wired consumers."""
from pathlib import Path


def load_preview_outputs(state,scope='latest',quality='original',stream='final',*,want_images=True):
    import torch
    from .preview import create_preview_plan
    from .cache_manager import ProjectCacheManager,load_frame_tensor
    from .media_io import resolve_input_path
    from .audio_post import slice_audio_frames,join_timeline_audio
    from .output_retention import assemble_frames
    info=create_preview_plan(state,scope,quality=quality,stream=stream)
    if not info.get('found'):raise ValueError('Generate a clip before using Smart Preview outputs.')
    manager=ProjectCacheManager(state['project_id'])
    import json
    plan=json.loads((Path(manager.project_dir)/'previews'/(info['key']+'.json')).read_text(encoding='utf-8'))
    chunks=[];audios=[];previous=None
    for row in plan['rows']:
        if row.get('source'):
            from .source_media import source_range
            source=source_range(row['source'],plan['source_state'],960,544,preserve_canvas=True)
            if source is None:raise ValueError('Preview source clip is unavailable.')
            frames,audio=source['frames'],source['audio']
        else:
            frames=load_frame_tensor(resolve_input_path(row['frames'],manager.project_dir))
            audio=torch.load(resolve_input_path(row['audio'],manager.project_dir),map_location='cpu',weights_only=True) if row.get('audio') else None
        start=max(0,int(row.get('trim_prefix',0)));end=len(frames)-max(0,int(row.get('trim_tail',0)))
        if end<=start:raise ValueError('Preview clip has no visible frames.')
        chunks.append(frames[start:end])
        if audio:audio=slice_audio_frames(audio,start,end)
        else:audio={'waveform':torch.zeros((1,2,round((end-start)/24*48000))),'sample_rate':48000}
        if previous is None or row['index']!=previous+1:audio.pop('seam_prefix',None)
        previous=row['index'];audios.append(audio)
    width=max(int(f.shape[2]) for f in chunks);height=max(int(f.shape[1]) for f in chunks)
    cap={'540p':(960,540),'720p':(1280,720),'1080p':(1920,1080)}.get(quality)
    ratio=min(1.,cap[0]/width,cap[1]/height) if cap else 1.
    canvas=(max(2,int(width*ratio)//2*2),max(2,int(height*ratio)//2*2))
    images=assemble_frames(chunks,manager.project_dir,canvas=canvas) if want_images else None
    sound=join_timeline_audio(audios,fade_ms=plan['fade_ms'],enable_gain_match=plan['gain_match'])
    return images,sound,24.0
