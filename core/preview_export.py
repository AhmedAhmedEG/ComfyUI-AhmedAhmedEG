"""Explicit downloads from existing preview data; never update preview caches."""
import json
from pathlib import Path
from types import SimpleNamespace


def export_cached_preview(project_id,key,directory,base_dir=None):
    import re
    from .cache_manager import get_cache_root_dir,safe_component
    from .preview_segments import playback_manifest
    if not re.fullmatch(r'[0-9a-f]{64}',key):raise ValueError('Invalid preview revision.')
    project_id=safe_component(project_id)
    root=Path(base_dir or get_cache_root_dir(create=False))/project_id
    combined=root/'previews'/(key+'.mp4')
    if combined.is_file():return str(combined)
    plan_path=combined.with_suffix('.json')
    if not plan_path.is_file():raise FileNotFoundError('The displayed preview revision is no longer available. Refresh the preview.')
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    if plan.get('project_id')!=project_id or plan.get('scope') not in ('latest','full'):
        raise ValueError('Invalid preview export plan.')
    manager=SimpleNamespace(project_id=project_id,project_dir=str(root))
    target=Path(directory)/'preview.mp4'
    try:
        manifest=playback_manifest(manager,plan,read_only=True)
        if manifest:
            remux_fragments(root,manifest,target)
            return str(target)
    except (FileNotFoundError,ValueError):
        # Mixed canvases or older fragments can use the original saved revision.
        # This is an explicit export to temporary storage, never a cache restore.
        target.unlink(missing_ok=True)
    from .preview import encode_preview
    return encode_preview(project_id,key,base_dir,output_path=target)


def remux_fragments(root,manifest,target):
    """Copy existing H264/AAC packets, respecting the player's visible trims."""
    import av
    import heapq
    from fractions import Fraction
    def path(part):return root/'previews'/(part['key']+'.mp4')
    first=manifest['videos'][0]
    with av.open(str(path(first))) as video_input,av.open(str(path(manifest['audio']))) as audio_input:
        template=video_input.streams.video[0]
        signature=(template.codec_context.name,template.width,template.height,template.codec_context.extradata)
        with av.open(str(target),'w',format='mp4',options={'movflags':'+faststart'}) as output:
            video=output.add_stream_from_template(template)
            audio=output.add_stream_from_template(audio_input.streams.audio[0])
            video.time_base=Fraction(1,12288);audio.time_base=audio_input.streams.audio[0].time_base
            def packets(container,stream,destination,offset,limit):
                base=stream.start_time or 0
                for packet in container.demux(stream):
                    if packet.pts is None or packet.dts is None:continue
                    time=(packet.pts-base)*packet.time_base
                    if time>=limit:continue
                    old_base=packet.time_base;new_base=destination.time_base
                    packet.pts=round((time+offset)/new_base)
                    packet.dts=round(((packet.dts-base)*old_base+offset)/new_base)
                    packet.duration=round(packet.duration*old_base/new_base)
                    packet.time_base=new_base;packet.stream=destination
                    yield packet.dts*new_base,packet
            def videos():
                offset=Fraction(0)
                for part in manifest['videos']:
                    with av.open(str(path(part))) as container:
                        stream=container.streams.video[0]
                        current=(stream.codec_context.name,stream.width,stream.height,stream.codec_context.extradata)
                        if current!=signature or stream.codec_context.has_b_frames:
                            raise ValueError('Preview fragments require canvas conversion.')
                        duration=Fraction(round(part['duration']*24),24)
                        yield from packets(container,stream,video,offset,duration)
                        offset+=duration
            sound=packets(audio_input,audio_input.streams.audio[0],audio,Fraction(0),Fraction(str(manifest['duration'])))
            for _,packet in heapq.merge(videos(),sound,key=lambda row:row[0]):output.mux(packet)
