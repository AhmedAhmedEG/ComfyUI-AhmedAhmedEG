"""Export cached project shots one at a time and assemble a native disk VIDEO."""
from __future__ import annotations
import json
import os
import subprocess
import tempfile
try:
    from ..core.cache_manager import ProjectCacheManager, safe_component
    from ..core.source_media import source_range
except ImportError:
    from core.cache_manager import ProjectCacheManager, safe_component
    from core.source_media import source_range
from .node_video_combine import MiniMaxH3VideoCombine, FFMPEG_PATH, resolve_output_path


class MiniMaxH3ProjectVideo:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"timeline": ("STRING", {"forceInput": True}),
            "project_id": ("STRING", {"default": "default_director"}),
            "stream": (["final", "first_pass", "pre_refine", "refine_pass", "original_source"],),
            "selection": (["all", "clip_ids"],),
            "fps": ("FLOAT", {"default": 24., "min": 1., "max": 120.}),
            "filename_prefix": ("STRING", {"default": "minimax/project"}),
            "export_individual_shots": ("BOOLEAN", {"default": True})},
            "optional": {"clip_ids": ("STRING", {"default":"", "tooltip":"Comma-separated clip IDs to export in timeline order when selection is clip_ids."}),
                "refine_pass": ("INT", {"default":1,"min":1,"max":9999}),
                "ref_pack": ("MMX_REF_PACK", {"tooltip":"Optional live pool for uncached original source footage."})}}
    RETURN_TYPES = ("VIDEO", "STRING")
    RETURN_NAMES = ("video", "shot_files_json")
    FUNCTION = "export"
    OUTPUT_NODE = True
    CATEGORY = "ComfyUI-AhmedAhmedEG"
    @classmethod
    def IS_CHANGED(cls, timeline, project_id, **kwargs):
        state = json.loads(timeline)
        manager = ProjectCacheManager(state.get("project_id") or project_id)
        return os.path.getmtime(manager.manifest_path) if os.path.exists(manager.manifest_path) else float("nan")

    def export(self, timeline, project_id, stream="final", selection="all", fps=24., filename_prefix="minimax/project", export_individual_shots=True, clip_ids="", ref_pack=None, refine_pass=1):
        import torch
        from comfy_api.latest import InputImpl
        state = json.loads(timeline)
        manager = ProjectCacheManager(state.get("project_id") or project_id)
        paths = []
        files = []
        canvas = None
        previous_rms = None
        shots = state.get("clips", [])
        import math
        if not math.isfinite(fps) or not 1 <= fps <= 120:
            raise ValueError("Export FPS must be between 1 and 120.")
        requested = {value.strip() for value in clip_ids.split(',') if value.strip()}
        known = {str(shot.get('id')) for shot in shots}
        if selection == 'clip_ids' and (not requested or requested-known):
            raise ValueError("Choose existing clip IDs for export.")
        if selection not in ('all','clip_ids','selected'):
            raise ValueError("Unknown export selection.")
        chosen = [(i,shot) for i,shot in enumerate(shots) if selection=='all' or
            selection=='clip_ids' and str(shot.get('id')) in requested or
            selection=='selected' and shot.get('selected',False)]
        chosen_indices={i for i,_ in chosen}
        ref_pool={row['id']:row for row in (ref_pack or {}).get('refs',[])}
        def load(shot,index):
            cid=safe_component(shot.get('id',f'clip_{index+1}'))
            original=stream=='original_source'
            frames=manager.load_clip_frames(cid) if stream=='final' or shot.get('locked') else manager.load_clip_pre_refine(cid)
            audio=manager.load_clip_audio(cid)
            if stream=='first_pass':
                meta=manager._manifest.get('first_pass',{}).get(cid)
                if not meta: raise ValueError(f'Clip {cid} has no first pass.')
                frames=manager._load_tensor_file(manager._clip_artifact_path(cid,'draft_frames',meta['generation']), mmap=True)
                audio=manager._load_tensor_file(manager._clip_artifact_path(cid,'draft_audio',meta['generation']))
            elif stream=='refine_pass':
                meta=manager._manifest.get('clips',{}).get(cid,{})
                row=next((r for r in meta.get('refine_passes',[]) if r['pass']==refine_pass),None)
                if row is None: raise ValueError(f'Clip {cid} has no refinement pass {refine_pass}.')
                frames=manager._load_tensor_file(os.path.join(manager.project_dir,row['frames']), mmap=True)
                audio=manager._load_tensor_file(os.path.join(manager.project_dir,row['audio']))

            # Locked pack footage is cached in its original canvas. Reuse it
            # without requiring a live graph or an invented file on disk.
            metadata=manager._manifest.get('clips',{}).get(cid,{})
            if original and metadata.get('has_source'):
                frames=manager._load_tensor_file(manager._clip_artifact_path(cid,'source_frames',metadata.get('generation')), mmap=True)
                audio=manager._load_tensor_file(manager._clip_artifact_path(cid,'source_audio',metadata.get('generation')))
            if original and not metadata.get('has_source') and not shot.get('locked') or frames is None:
                source=source_range(shot,state,int(state.get('width',1344)),int(state.get('height',768)),
                    preserve_canvas=True,ref_pool=ref_pool)
                if source is None: raise ValueError(f"Clip {cid} has no {stream} cache or source range.")
                frames,audio=source['original_frames'],source['audio']
            if not original and not shot.get('locked'):
                meta=manager._manifest.get('first_pass' if stream=='first_pass' else 'clips',{}).get(cid,{})
                prefix=int(meta.get('trim_prefix',0))
                tail=0
                if index+1 in chosen_indices:
                    next_id=safe_component(shots[index+1].get('id',f'clip_{index+2}'))
                    tail=int(manager._manifest.get('clips',{}).get(next_id,{}).get('previous_trim',0))
                end=frames.shape[0]-tail
                if end<=prefix: raise ValueError(f"Clip {cid} has no visible frames after trimming.")
                frames=frames[prefix:end]
                if audio:
                    rate=audio['sample_rate']
                    audio={**audio,'waveform':audio['waveform'][...,round(prefix/24*rate):round(end/24*rate)]}
            return frames,audio
        # Two bounded passes avoid holding the complete decoded sequence.
        sizes=[]
        for index,shot in chosen:
            frames,_=load(shot,index)
            sizes.append((int(frames.shape[2]),int(frames.shape[1])))
            del frames
        if sizes: canvas=(max(w for w,h in sizes),max(h for w,h in sizes))
        for index, shot in chosen:
            frames,audio=load(shot,index)
            incoming_rms = float(previous_rms) if previous_rms is not None else None
            if fps != 24:
                count = max(1, round(frames.shape[0]*fps/24))
                indices = torch.arange(count, device=frames.device).mul(24/fps).long().clamp(max=frames.shape[0]-1)
                frames = frames[indices]
            if (frames.shape[2], frames.shape[1]) != canvas:
                try:
                    from ..core.output_retention import assemble_frames
                except ImportError:
                    from core.output_retention import assemble_frames
                frames=assemble_frames([frames],manager.project_dir,canvas=canvas)
            if audio:
                try:
                    from ..core.audio_post import concatenate_audio_clips
                except ImportError:
                    from core.audio_post import concatenate_audio_clips
                processed = concatenate_audio_clips([audio],crossfade_ms=0,enable_gain_match=False,
                    enable_declick=False)
                wave = processed["waveform"]
                if previous_rms is not None and state.get("audio_gain_match",True):
                    current_rms = torch.sqrt(torch.mean(wave**2)+1e-8)
                    gain = (previous_rms/current_rms).clamp(10**(-6/20),10**(6/20))
                    wave = wave*gain
                fade = float(state.get("audio_fade_ms",15))
                if fade > 0:
                    try:
                        from ..core.audio_post import apply_audio_fade
                    except ImportError:
                        from core.audio_post import apply_audio_fade
                    wave = apply_audio_fade(wave,48000,fade,fade)
                previous_rms = torch.sqrt(torch.mean(wave**2)+1e-8)
                audio = {"waveform":wave,"sample_rate":48000}
            try:
                from ..core.segment_exports import encoded_segment_path, commit_encoded_segment
            except ImportError:
                from core.segment_exports import encoded_segment_path, commit_encoded_segment
            import shutil
            cid=safe_component(shot.get('id',f'clip_{index+1}'))
            meta=manager._manifest.get('first_pass' if stream=='first_pass' else 'clips',{}).get(cid,{})
            cached_path=encoded_segment_path(manager,cid,{
                'version':1,'stream':stream,'refine_pass':refine_pass,'fps':fps,'canvas':canvas,
                'metadata':meta,'selection':sorted(chosen_indices),'index':index,
                'next_metadata':manager._manifest.get('clips',{}).get(str(shots[index+1].get('id')), {}) if index+1 in chosen_indices else None,
                'fade':state.get('audio_fade_ms',15),'gain_match':state.get('audio_gain_match',True),
                'incoming_rms':incoming_rms}) if meta.get('generation') else None
            if cached_path is not None and cached_path.is_file():
                path=str(cached_path)
                if export_individual_shots:
                    path,filename,subfolder=resolve_output_path(f'{filename_prefix}/shot_{index+1}_{stream}','mp4',True)
                    shutil.copyfile(cached_path,path)
                    files.append({'filename':filename,'subfolder':subfolder,'type':'output','format':'video/mp4'})
            else:
                result = MiniMaxH3VideoCombine().combine_video(frames, audio=audio, frame_rate=fps,
                    filename_prefix=f"{filename_prefix}/shot_{index+1}_{stream}", save_output=export_individual_shots,
                    codec="H.264", container="mp4", bit_depth="8-bit")
                path = result["result"][1]
                files.extend(result["ui"]["video"])
                if cached_path is not None and os.path.isfile(path):
                    commit_encoded_segment(path,cached_path)
                    if not export_individual_shots: path=str(cached_path)
            paths.append(path)
            del frames, audio
        if not paths: raise ValueError("There are no shots to export for this selection.")
        if not FFMPEG_PATH: raise RuntimeError("Project assembly requires an available FFmpeg executable.")
        final, filename, subfolder = resolve_output_path(filename_prefix + "_" + stream, "mp4", True)
        fd, listing = tempfile.mkstemp(suffix=".txt", dir=manager.project_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                for path in paths:
                    output.write("file '" + path.replace("\\", "/").replace("'", "'\\''") + "'\n")
            result = subprocess.run([FFMPEG_PATH, "-y", "-f", "concat", "-safe", "0", "-i", listing,
                "-c", "copy", final], capture_output=True)
            if result.returncode: raise RuntimeError(result.stderr.decode(errors="replace")[-4000:])
        finally:
            os.unlink(listing)
        preview = {"filename": filename, "subfolder": subfolder, "type": "output", "format": "video/mp4"}
        return {"ui": {"video": [preview]}, "result": (InputImpl.VideoFromFile(final), json.dumps(files))}
