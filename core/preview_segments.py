"""Reusable video fragments plus a small, join-correct timeline soundtrack."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import urlencode


def _save_plan(manager, plan):
    key = hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    path = Path(manager.project_dir) / 'previews' / (key + '.json')
    if not path.exists():
        fd, temporary = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as output: json.dump(plan, output)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)
    return {'key': key, 'path': '/minimax_director/preview/segment?' + urlencode({'project_id':manager.project_id,'key':key})}


def playback_manifest(manager, plan):
    from .cache_manager import load_frame_tensor
    from .media_io import resolve_input_path
    if any(row.get('source') for row in plan['rows']): return None
    videos, duration = [], 0.
    for row in plan['rows']:
        # Reuse the exact same video fragment in Latest and Full. Full can trim
        # the predecessor's handoff with MediaSource's append window.
        frame_count=row.get('frame_count')
        if frame_count is None:
            frames = load_frame_tensor(resolve_input_path(row['frames'], manager.project_dir))
            frame_count=int(frames.shape[0]);del frames
        count = int(frame_count) - int(row.get('trim_prefix', 0))
        visible = count - int(row.get('trim_tail', 0))
        if visible < 1: raise ValueError('Cached clip has no visible frames.')
        canonical = {**row, 'trim_tail':0, 'previous_trim':0, 'index':0}
        video_plan = {'version':1,'kind':'video_fragment','project_id':manager.project_id,
                      'stream':plan['stream'],'quality':plan['quality'],'rows':[canonical]}
        # Names/order/update timestamps do not alter the encoded pixels.
        for field in ('name','updated_at','audio'): video_plan['rows'][0].pop(field, None)
        descriptor = _save_plan(manager, video_plan)
        descriptor.update(duration=visible/24, clip_id=row['clip_id'],
                          generations={row['clip_id']:row['generation']})
        videos.append(descriptor); duration += visible/24
    audio_plan = {key:plan[key] for key in ('project_id','stream','rows','gain_match','fade_ms')}
    audio_plan.update(kind='audio_fragment',version=2)
    audio = _save_plan(manager, audio_plan)
    audio['generations'] = {row['clip_id']:row['generation'] for row in plan['rows']}
    return {'videos':videos,'audio':audio,'duration':duration,
            'video_mime':'video/mp4; codecs="avc1.640033"',
            'audio_mime':'audio/mp4; codecs="mp4a.40.2"'}


def encode_fragment(project_id, key, base_dir=None):
    import av
    import torch
    import torch.nn.functional as F
    import numpy as np
    from .preview import preview_path
    from .cache_manager import load_frame_tensor
    from .media_io import resolve_input_path
    from .audio_post import slice_audio_frames, join_timeline_audio
    from .vendor.dasiwa.helper_pyav_video import _configure_video_stream, _video_frame, _configure_audio_stream, _encode_audio
    from fractions import Fraction
    manager, target = preview_path(project_id, key, base_dir)
    if target.exists(): return str(target)
    plan = json.loads(target.with_suffix('.json').read_text(encoding='utf-8'))
    kind = plan.get('kind')
    if kind not in ('video_fragment','audio_fragment'): raise ValueError('Not a playback fragment.')
    fd, temporary = tempfile.mkstemp(dir=target.parent, suffix='.mp4'); os.close(fd)
    try:
        with av.open(temporary, 'w', format='mp4', options={'movflags':'frag_keyframe+empty_moov+default_base_moof'}) as container:
            if kind == 'video_fragment':
                row = plan['rows'][0]
                frames = load_frame_tensor(resolve_input_path(row['frames'], manager.project_dir))
                frames = frames[int(row.get('trim_prefix',0)):]
                ih, iw = int(frames.shape[1]), int(frames.shape[2])
                cap = {'540p':(960,540),'720p':(1280,720),'1080p':(1920,1080)}.get(plan['quality'])
                scale = min(1., cap[0]/iw, cap[1]/ih) if cap else 1.
                width, height = max(2,int(iw*scale)//2*2), max(2,int(ih*scale)//2*2)
                if width > 4096 or height > 2304: raise ValueError('Canvas requires ordinary streaming fallback.')
                stream = _configure_video_stream(container,'libx264',width,height,24,8,23)
                stream.options = {**stream.options,'preset':'veryfast','profile':'high','level':'5.1','bf':'0','g':'24'}
                stream.codec_context.thread_count = 2
                for index, image in enumerate(frames):
                    if (height,width) != (ih,iw):
                        image = F.interpolate(image.permute(2,0,1)[None],size=(height,width),mode='bilinear',align_corners=False)[0].permute(1,2,0)
                    pixels = (image[...,:3].clamp(0,1).numpy()*255).round().astype(np.uint8)
                    for packet in stream.encode(_video_frame(pixels,index,Fraction(24),8)): container.mux(packet)
                for packet in stream.encode(None): container.mux(packet)
            else:
                audios = []
                for index,row in enumerate(plan['rows']):
                    frames = load_frame_tensor(resolve_input_path(row['frames'],manager.project_dir))
                    start, end = int(row.get('trim_prefix',0)), int(frames.shape[0])-int(row.get('trim_tail',0))
                    if row.get('audio'):
                        sound = torch.load(resolve_input_path(row['audio'],manager.project_dir),map_location='cpu',weights_only=True)
                        sound = slice_audio_frames(sound,start,end)
                    else: sound = {'waveform':torch.zeros((1,2,round((end-start)/24*48000))),'sample_rate':48000}
                    if index == 0 or row['index'] != plan['rows'][index-1]['index']+1: sound.pop('seam_prefix',None)
                    audios.append(sound); del frames
                joined = join_timeline_audio(audios,fade_ms=plan['fade_ms'],enable_gain_match=plan['gain_match'])
                wave, rate = joined['waveform'][0].numpy(), int(joined['sample_rate'])
                stream, target_rate = _configure_audio_stream(container,'aac',rate,wave.shape[0],'128k')
                stream.codec_context.thread_count = 1
                _encode_audio(container,stream,(wave,rate),target_rate)
        os.replace(temporary,target)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
    return str(target)
