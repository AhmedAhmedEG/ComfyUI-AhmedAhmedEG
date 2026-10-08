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
            "stream": (["final", "pre_refine", "original_source"],),
            "selection": (["all", "selected"],),
            "fps": ("FLOAT", {"default": 24., "min": 1., "max": 120.}),
            "filename_prefix": ("STRING", {"default": "minimax/project"}),
            "export_individual_shots": ("BOOLEAN", {"default": True})}}
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

    def export(self, timeline, project_id, stream="final", selection="all", fps=24., filename_prefix="minimax/project", export_individual_shots=True):
        import torch
        from comfy_api.latest import InputImpl
        state = json.loads(timeline)
        manager = ProjectCacheManager(state.get("project_id") or project_id)
        paths = []
        files = []
        canvas = None
        previous_rms = None
        shots = state.get("clips", [])
        for index, shot in enumerate(shots):
            if selection == "selected" and not shot.get("selected", True): continue
            cid = safe_component(shot.get("id", f"clip_{index+1}"))
            if stream == "original_source" or shot.get("locked"):
                source = source_range(shot, state, int(state.get("width", 1344)), int(state.get("height", 768)), preserve_canvas=stream == "original_source")
                if source is None: raise ValueError(f"Shot {cid} has no source range.")
                frames, audio = source["frames"], source["audio"]
            else:
                frames = manager.load_clip_frames(cid) if stream == "final" else manager.load_clip_pre_refine(cid)
                audio = manager.load_clip_audio(cid)
                if frames is None:
                    source = source_range(shot, state, int(state.get("width", 1344)), int(state.get("height", 768)))
                    if source is None: raise ValueError(f"Shot {cid} has no {stream} cache or source range.")
                    frames, audio = source["frames"], source["audio"]
                meta = manager._manifest.get("clips", {}).get(cid, {})
                prefix = int(meta.get("trim_prefix", 0))
                if prefix and frames.shape[0] > prefix:
                    frames = frames[prefix:]
                    if audio:
                        audio = {**audio, "waveform": audio["waveform"][..., round(prefix/24*audio["sample_rate"]):]}
                if index + 1 < len(shots) and (selection == "all" or shots[index+1].get("selected", True)):
                    next_id = safe_component(shots[index+1].get("id", f"clip_{index+2}"))
                    tail_trim = int(manager._manifest.get("clips", {}).get(next_id, {}).get("previous_trim", 0))
                    if tail_trim and frames.shape[0] > tail_trim:
                        frames = frames[:-tail_trim]
                        if audio:
                            audio = {**audio, "waveform": audio["waveform"][..., :round(frames.shape[0]/24*audio["sample_rate"])]}
            if fps != 24:
                count = max(1, round(frames.shape[0]*fps/24))
                indices = torch.arange(count, device=frames.device).mul(24/fps).long().clamp(max=frames.shape[0]-1)
                frames = frames[indices]
            if canvas is None: canvas = (frames.shape[2], frames.shape[1])
            if (frames.shape[2], frames.shape[1]) != canvas:
                try:
                    from ..core.media_io import scale_tensor_image
                except ImportError:
                    from core.media_io import scale_tensor_image
                frames = scale_tensor_image(frames, "Fit and pad", *canvas)
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
            result = MiniMaxH3VideoCombine().combine_video(frames, audio=audio, frame_rate=fps,
                filename_prefix=f"{filename_prefix}/shot_{index+1}_{stream}", save_output=export_individual_shots,
                codec="H.264", container="mp4", bit_depth="8-bit")
            path = result["result"][1]
            paths.append(path); files.extend(result["ui"]["video"])
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
