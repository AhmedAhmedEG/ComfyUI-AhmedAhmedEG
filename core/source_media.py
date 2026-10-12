"""Source timeline ranges and original-audio policy for native H3 edits."""
from __future__ import annotations
import math
import torch
from .config import FPS
from .media_io import load_video, load_audio, scale_tensor_image
from .audio_post import fit_audio_duration


def video_input_dimensions(width, height, settings=None):
    """H3 reference budget: 768 short edge, 768*1344 pixels, 32px grid.

    Custom budgets only reduce the native reference size; they do not upscale
    small footage or change the generation canvas. MP means 1,000,000 pixels.
    """
    width, height = int(width), int(height)
    if min(width, height) < 32:
        raise ValueError("Video input dimensions must be at least 32 pixels.")
    settings = settings or {}
    mode = settings.get("mode", "auto")
    scale = min(1.0, 768 / min(width, height), math.sqrt((768 * 1344) / (width * height)))
    if mode == "short_edge":
        edge = float(settings.get("short_edge", 768))
        if not math.isfinite(edge) or not 32 <= edge <= 768:
            raise ValueError("Video input short edge must be between 32 and 768 pixels.")
        scale = min(scale, edge / min(width, height))
    elif mode == "megapixels":
        mp = float(settings.get("megapixels", 1.032192))
        if not math.isfinite(mp) or not .001024 <= mp <= 1.032192:
            raise ValueError("Video input budget must be between 0.001024 and 1.032192 megapixels.")
        scale = min(scale, math.sqrt(mp * 1_000_000 / (width * height)))
    elif mode != "auto":
        raise ValueError("Unknown video input resolution mode.")
    snap = round if mode == "auto" else math.floor
    return (max(32, min(width // 32 * 32, snap(width * scale / 32) * 32)),
            max(32, min(height // 32 * 32, snap(height * scale / 32) * 32)))


def source_range(shot, timeline, width, height, preserve_canvas=False):
    source = shot.get("source", timeline.get("source"))
    if not source:
        return None
    if isinstance(source, str):
        source = {"filename": source}
    if not isinstance(source, dict) or not source.get("filename"):
        raise ValueError("Source video must specify a filename in ComfyUI input.")
    start = float(shot.get("source_start", source.get("start", 0)))
    end = float(shot.get("source_end", start + float(shot.get("duration", 5))))
    if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start:
        raise ValueError("Source range must have finite start/end times with end > start >= 0.")
    import folder_paths
    root = folder_paths.get_input_directory()
    frames = load_video(source["filename"], input_directory=root, trim_start=start,
        trim_end=end, target_fps=FPS)
    model_frames = frames
    if not preserve_canvas:
        input_width, input_height = video_input_dimensions(frames.shape[2], frames.shape[1], shot.get("video_input_resolution"))
        model_frames = scale_tensor_image(frames, "Target", input_width, input_height)
    if not preserve_canvas:
        frames = scale_tensor_image(frames, "Fit and pad", width, height)
    try:
        audio = load_audio(source["filename"], input_directory=root, trim_start=start, trim_end=end)
    except ValueError as exc:
        if "no audio stream" not in str(exc).lower():
            raise
        audio = {"waveform": torch.zeros((1, 2, round(frames.shape[0] / FPS * 48000))), "sample_rate": 48000}
    return {"frames": frames, "model_frames": model_frames, "audio": fit_audio_duration(audio, frames.shape[0], FPS),
        "filename": source["filename"], "start": start, "end": end}


def choose_audio(mode, generated, source, frame_count):
    mode = str(mode or "generate").lower()
    if mode == "generate":
        return fit_audio_duration(generated, frame_count, FPS)
    if mode in ("source", "keep_source", "original"):
        if source is None:
            raise ValueError("Keep source audio requires a source video range.")
        return fit_audio_duration(source["audio"], frame_count, FPS)
    if mode == "mute":
        return {"waveform": torch.zeros((1, 2, round(frame_count / FPS * 48000))), "sample_rate": 48000}
    raise ValueError(f"Unknown shot audio mode: {mode!r}")


def continuation_range(clip, width, height):
    """Decode just the requested ending of a clip's explicit continuation video."""
    source = clip.get("continuation_source")
    if not source:
        return None
    if not isinstance(source, dict) or not source.get("filename"):
        raise ValueError("Continuation video must specify an input filename and end time.")
    end = float(source.get("end", 0))
    if not math.isfinite(end) or end <= 0:
        raise ValueError("Continuation video end time must be finite and positive.")
    return source_range({"source": source, "source_start": max(0, end - 56 / FPS),
                         "source_end": end}, {}, width, height)
