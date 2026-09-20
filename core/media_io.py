"""High-precision Media I/O and preprocessing for MiniMax H3 Master Director."""

from __future__ import annotations

import os
import math
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

from .config import (
    FPS,
    AUDIO_SAMPLE_RATE,
    CANVAS_MULTIPLE,
    REF_IMAGE_SHORT_EDGE,
    snap_to_multiple,
)

SCALING_MODES = (
    "Off",
    "Auto",
    "Target",
    "Fit",
    "Fill and crop",
    "Fit and pad",
)


def resolve_input_path(relative_or_absolute_path: str, input_directory: Optional[str] = None) -> str:
    """Resolve a media path safely. If input_directory is provided, prevents path escape."""
    path = str(relative_or_absolute_path or "").strip()
    if not path:
        raise ValueError("Media path must be non-empty.")
    
    if os.path.isabs(path) and os.path.isfile(path):
        return os.path.realpath(path)

    if input_directory:
        root = os.path.realpath(input_directory)
        candidate = os.path.realpath(os.path.join(root, path))
        if os.path.commonpath((root, candidate)) != root:
            raise ValueError(f"Media path escapes the ComfyUI input directory: {path}")
        if os.path.isfile(candidate):
            return candidate

    if os.path.isfile(path):
        return os.path.realpath(path)

    raise FileNotFoundError(f"Media file not found: {path}")


def scale_tensor_image(
    image: torch.Tensor,
    mode: str,
    target_width: int,
    target_height: int,
) -> torch.Tensor:
    """Scale a [B, H, W, C] float32 image tensor according to selected mode."""
    if mode == "Off" or not hasattr(image, "shape") or image.ndim != 4:
        return image

    b, h, w, c = image.shape
    # Convert to [B, C, H, W] for PyTorch F.interpolate
    tensor = image.permute(0, 3, 1, 2)

    if mode == "Auto":
        # Preserve aspect ratio, but downscale short edge if > REF_IMAGE_SHORT_EDGE (2048)
        short_edge = min(h, w)
        if short_edge <= REF_IMAGE_SHORT_EDGE:
            return image
        scale = float(REF_IMAGE_SHORT_EDGE) / float(short_edge)
        new_w = snap_to_multiple(round(w * scale), CANVAS_MULTIPLE)
        new_h = snap_to_multiple(round(h * scale), CANVAS_MULTIPLE)
        resized = F.interpolate(tensor, size=(new_h, new_w), mode="bilinear", align_corners=False)
        return resized.permute(0, 2, 3, 1).contiguous()

    target_w = snap_to_multiple(target_width, CANVAS_MULTIPLE)
    target_h = snap_to_multiple(target_height, CANVAS_MULTIPLE)

    if mode == "Target":
        # Direct stretch to target canvas
        resized = F.interpolate(tensor, size=(target_h, target_w), mode="bilinear", align_corners=False)
        return resized.permute(0, 2, 3, 1).contiguous()

    if mode == "Fit":
        # Fit entirely within target canvas, snapping to divisible grid
        scale = min(target_w / w, target_h / h)
        new_w = snap_to_multiple(round(w * scale), CANVAS_MULTIPLE)
        new_h = snap_to_multiple(round(h * scale), CANVAS_MULTIPLE)
        resized = F.interpolate(tensor, size=(new_h, new_w), mode="bilinear", align_corners=False)
        return resized.permute(0, 2, 3, 1).contiguous()

    if mode == "Fill and crop":
        # Cover target canvas completely and center-crop overflow
        scale = max(target_w / w, target_h / h)
        scale_w = round(w * scale)
        scale_h = round(h * scale)
        resized = F.interpolate(tensor, size=(scale_h, scale_w), mode="bilinear", align_corners=False)
        # Center crop to target_h, target_w
        start_y = max(0, (scale_h - target_h) // 2)
        start_x = max(0, (scale_w - target_w) // 2)
        cropped = resized[:, :, start_y : start_y + target_h, start_x : start_x + target_w]
        return cropped.permute(0, 2, 3, 1).contiguous()

    if mode == "Fit and pad":
        # Fit inside canvas, pad borders with black to reach target_w, target_h exactly
        scale = min(target_w / w, target_h / h)
        new_w = snap_to_multiple(round(w * scale), 2)
        new_h = snap_to_multiple(round(h * scale), 2)
        resized = F.interpolate(tensor, size=(new_h, new_w), mode="bilinear", align_corners=False)
        pad_x = (target_w - new_w) // 2
        pad_y = (target_h - new_h) // 2
        padded = F.pad(resized, (pad_x, target_w - new_w - pad_x, pad_y, target_h - new_h - pad_y), value=0.0)
        return padded.permute(0, 2, 3, 1).contiguous()

    return image


def load_image(
    path: str,
    input_directory: Optional[str] = None,
    scaling_mode: str = "Auto",
    target_width: int = 1344,
    target_height: int = 768,
) -> torch.Tensor:
    """Load an image file and return float32 tensor [1, H, W, 3] in range [0, 1]."""
    full_path = resolve_input_path(path, input_directory)
    with Image.open(full_path) as img:
        rgb = img.convert("RGB")
        array = np.asarray(rgb, dtype=np.float32) / 255.0
    tensor = torch.from_numpy(array).unsqueeze(0)
    return scale_tensor_image(tensor, scaling_mode, target_width, target_height)


def decode_audio_frame(frame) -> np.ndarray:
    """Safely decode one PyAV audio frame into float32 array shaped (channels, samples).
    
    Handles planar formats (fltp) and packed interleaved formats (s16) to avoid
    the classic stereo length doubling bug.
    """
    samples = frame.to_ndarray()
    if samples.ndim == 1:
        samples = samples[None, :]
    channels = samples.shape[-1] // frame.samples if frame.samples else 1
    if channels > 1 and samples.shape[0] == 1:
        # Interleaved format: reshape and transpose
        samples = np.ascontiguousarray(samples.reshape(-1, channels).T)

    if samples.dtype.kind == "u":
        midpoint = 2.0 ** (8 * samples.dtype.itemsize - 1)
        samples = (samples.astype(np.float32) - midpoint) / midpoint
    elif samples.dtype.kind != "f":
        samples = samples.astype(np.float32) / -float(np.iinfo(samples.dtype).min)
    return samples


def load_audio(
    path: str,
    input_directory: Optional[str] = None,
    trim_start: float = 0.0,
    trim_end: Optional[float] = None,
) -> Dict[str, Any]:
    """Load and trim an audio file. Returns ComfyUI standard audio dict."""
    full_path = resolve_input_path(path, input_directory)
    try:
        import av
    except ImportError as exc:
        raise RuntimeError("MiniMax H3 Director requires the 'av' (PyAV) package for audio.") from exc

    if trim_start < 0.0 or (trim_end is not None and trim_end <= trim_start):
        raise ValueError(f"Invalid audio trim range: start={trim_start}, end={trim_end}")

    container = av.open(full_path)
    try:
        stream = next((s for s in container.streams if s.type == "audio"), None)
        if stream is None:
            raise ValueError(f"Audio file has no audio stream: {path}")

        sample_rate = int(stream.rate or AUDIO_SAMPLE_RATE)
        chunks: List[torch.Tensor] = []

        for frame in container.decode(stream):
            timestamp = float(frame.pts * frame.time_base) if frame.pts is not None else 0.0
            frame_end = timestamp + float(frame.samples) / sample_rate
            if frame_end <= trim_start or (trim_end is not None and timestamp >= trim_end):
                continue

            samples = decode_audio_frame(frame)
            start_idx = max(0, int(round((trim_start - timestamp) * sample_rate)))
            end_idx = samples.shape[-1] if trim_end is None else min(samples.shape[-1], int(round((trim_end - timestamp) * sample_rate)))

            if end_idx > start_idx:
                chunks.append(torch.from_numpy(samples[:, start_idx:end_idx]).float())

        if not chunks:
            raise ValueError(f"Audio trim range produced no samples for {path}")

        waveform = torch.cat(chunks, dim=-1).unsqueeze(0)  # [1, channels, samples]
        return {"waveform": waveform, "sample_rate": sample_rate}
    finally:
        container.close()


def load_embedded_video_audio(
    path: str,
    input_directory: Optional[str] = None,
    trim_start: float = 0.0,
    trim_end: Optional[float] = None,
) -> Dict[str, Any]:
    """Decode embedded audio stream from a video container with exact trim alignment."""
    return load_audio(path, input_directory=input_directory, trim_start=trim_start, trim_end=trim_end)


def load_video(
    path: str,
    input_directory: Optional[str] = None,
    trim_start: float = 0.0,
    trim_end: Optional[float] = None,
    target_fps: float = FPS,
    scaling_mode: str = "Off",
    target_width: int = 1344,
    target_height: int = 768,
) -> torch.Tensor:
    """Decode a video to an IMAGE tensor [T, H, W, 3] at fixed target_fps.
    
    Uses presentation timestamp (PTS) search (nearest PTS match) so videos
    recorded at 30, 60, or variable fps are perfectly resampled without slow-mo.
    """
    full_path = resolve_input_path(path, input_directory)
    try:
        import av
    except ImportError as exc:
        raise RuntimeError("MiniMax H3 Director requires the 'av' (PyAV) package for video.") from exc

    if trim_start < 0.0 or (trim_end is not None and trim_end <= trim_start):
        raise ValueError(f"Invalid video trim range: start={trim_start}, end={trim_end}")

    container = av.open(full_path)
    try:
        stream = next((s for s in container.streams if s.type == "video"), None)
        if stream is None:
            raise ValueError(f"Video file contains no video stream: {path}")

        duration = None
        if stream.duration is not None and stream.time_base is not None:
            duration = float(stream.duration * stream.time_base)
        if duration is None and container.duration is not None:
            duration = float(container.duration) / float(av.time_base)
        if duration is None:
            raise ValueError(f"Could not determine video duration for {path}")

        end_time = duration if trim_end is None else min(float(trim_end), duration)
        if end_time <= trim_start:
            raise ValueError(f"Trim end ({end_time}s) <= trim start ({trim_start}s)")

        # Target ticks
        timestamps = np.arange(float(trim_start), end_time, 1.0 / float(target_fps))
        timestamps = timestamps[timestamps < end_time]
        if timestamps.size == 0:
            raise ValueError(f"Trim range produced zero frames at {target_fps} fps")

        frames: List[torch.Tensor] = []
        source_times: List[float] = []

        for frame in container.decode(stream):
            pts = float(frame.pts * frame.time_base) if frame.pts is not None else None
            if pts is None or pts < trim_start or pts >= end_time:
                continue
            frames.append(torch.from_numpy(frame.to_rgb().to_ndarray()).float() / 255.0)
            source_times.append(pts)

        if not frames:
            raise ValueError(f"No frames decoded in trim range [{trim_start}, {end_time})")

        source_batch = torch.stack(frames)  # [N_src, H, W, 3]

        # Nearest PTS match
        ticks = torch.as_tensor(timestamps, dtype=torch.float64)
        times = torch.as_tensor(source_times, dtype=torch.float64)
        pos = torch.searchsorted(times, ticks)
        right = pos.clamp(max=len(times) - 1)
        left = (pos - 1).clamp(min=0)
        nearest_indices = torch.where((ticks - times[left]).abs() <= (times[right] - ticks).abs(), left, right)

        resampled_batch = source_batch[nearest_indices]

        if scaling_mode != "Off":
            resampled_batch = scale_tensor_image(resampled_batch, scaling_mode, target_width, target_height)

        return resampled_batch
    finally:
        container.close()


def resample_image_batch_fps(
    frames: torch.Tensor,
    source_fps: float,
    target_fps: float = FPS,
) -> torch.Tensor:
    """Resample an in-memory IMAGE batch [T, H, W, 3] from source_fps to target_fps preserving duration."""
    if abs(source_fps - target_fps) < 1e-3 or frames.shape[0] <= 1:
        return frames

    total_frames = int(frames.shape[0])
    duration = total_frames / float(source_fps)
    target_count = max(1, round(duration * float(target_fps)))

    # Nearest neighbor temporal resampling indices
    indices = torch.linspace(0, total_frames - 1, steps=target_count).round().long().clamp(0, total_frames - 1)
    return frames[indices]
