"""Segment continuity, latent slicing, prefix trimming, and seam color grading."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

import torch

from .config import FPS, AUDIO_LATENT_FPS, DEFAULT_CONTEXT_FRAMES

log = logging.getLogger("MiniMaxH3MasterDirector.continuity")


def unpack_av_samples(samples: Any) -> Tuple[List[torch.Tensor], bool]:
    """Safely split AV streams without confusing Tensor.unbind (batch axis) with NestedTensor.unbind."""
    if samples is None:
        raise ValueError("Cannot unpack None samples.")
    if hasattr(samples, "is_nested") and samples.is_nested:
        return list(samples.unbind()), True
    if isinstance(samples, (tuple, list)):
        return list(samples), True
    if hasattr(samples, "unbind") and not isinstance(samples, torch.Tensor):
        return list(samples.unbind()), True
    return [samples], False


def extract_streams_from_av_latent(latent_dict: Dict[str, Any]) -> Tuple[torch.Tensor, torch.Tensor]:
    """Extract video and audio latent tensors from ComfyUI MiniMax H3 AV latent dict."""
    samples = latent_dict.get("samples")
    if samples is None:
        raise ValueError("Invalid latent dict: missing 'samples' key.")

    streams, is_nested = unpack_av_samples(samples)

    if len(streams) < 2:
        video_stream = streams[0]
        if video_stream.ndim == 4:
            video_stream = video_stream.unsqueeze(0)
        t_v = video_stream.shape[2] if video_stream.ndim == 5 else 5
        pixel_frames = 5 if t_v <= 2 else ((t_v - 2) // 5) * 17 + 5
        audio_stream = torch.zeros((1, 32, 2, max(1, round(pixel_frames * AUDIO_LATENT_FPS / FPS))), device=video_stream.device, dtype=video_stream.dtype)
    else:
        video_stream = streams[0]
        audio_stream = streams[1]

    if video_stream.ndim == 4:
        video_stream = video_stream.unsqueeze(0)  # [1, C, T, H, W]

    return video_stream, audio_stream


def repack_av_latent(video_stream: torch.Tensor, audio_stream: torch.Tensor) -> Dict[str, Any]:
    """Repack video and audio tensors into ComfyUI NestedTensor AV latent dict."""
    try:
        import comfy.nested_tensor
        samples = comfy.nested_tensor.NestedTensor(tuple([video_stream, audio_stream]))
    except Exception:
        # Fallback to tuple if NestedTensor class is unavailable
        samples = tuple([video_stream, audio_stream])

    return {"samples": samples}


def trim_continuity_prefix(
    decoded_frames: torch.Tensor,
    context_frames: int = DEFAULT_CONTEXT_FRAMES,
) -> torch.Tensor:
    """Trim the pinned prefix frames from freshly decoded video tensor [T, H, W, C]."""
    if decoded_frames.shape[0] <= context_frames:
        log.warning(
            f"Decoded frames ({decoded_frames.shape[0]}) <= context_frames ({context_frames}); keeping all."
        )
        return decoded_frames

    return decoded_frames[context_frames:].clone()


def trim_continuity_audio_prefix(
    audio_dict: Dict[str, Any],
    context_frames: int = DEFAULT_CONTEXT_FRAMES,
) -> Dict[str, Any]:
    """Trim the pinned prefix duration from freshly decoded audio waveform."""
    wf = audio_dict["waveform"]
    sr = int(audio_dict.get("sample_rate", 48000))

    trim_duration = context_frames / FPS
    trim_samples = int(round(trim_duration * sr))

    if wf.shape[-1] <= trim_samples:
        return audio_dict

    trimmed_wf = wf[..., trim_samples:].clone()
    return {"waveform": trimmed_wf, "sample_rate": sr}


def match_color_temperature_and_grade(
    current_frames: torch.Tensor,
    prev_tail_frames: torch.Tensor,
    blend_window: int = 12,
) -> torch.Tensor:
    """Subtly align the color grading and luminance of opening frames to previous tail to eliminate cut flicker."""
    if current_frames is None or prev_tail_frames is None:
        return current_frames
    if current_frames.shape[0] == 0 or prev_tail_frames.shape[0] == 0:
        return current_frames

    # Compute channel means on tail and opening
    tail_sample = prev_tail_frames[-min(10, prev_tail_frames.shape[0]):].float()
    open_sample = current_frames[:min(10, current_frames.shape[0])].float()

    mean_tail = tail_sample.mean(dim=(0, 1, 2))  # [3]
    mean_open = open_sample.mean(dim=(0, 1, 2))  # [3]

    gain = (mean_tail / (mean_open + 1e-6)).clamp(0.7, 1.4)  # Limit correction factor

    out = current_frames.clone().float()
    window = min(blend_window, out.shape[0])

    # Linear falloff ramp from gain -> 1.0
    ramp = torch.linspace(1.0, 0.0, steps=window, device=out.device).view(-1, 1, 1, 1)
    gain_tensor = gain.to(out.device).view(1, 1, 1, -1)

    # Blend correction into the opening frames
    out[:window] = out[:window] * (1.0 + ramp * (gain_tensor - 1.0))
    return out.clamp(0.0, 1.0)


# Per-shot continuity policy, with legacy global configuration fallback.
MODES = ("Independent (No Continuity)", "Motion Context (Chained)",
         "Latent Carry (Pinned)", "FL2VA Tail Handoff")
GRID = (5, 22, 39, 56)


def resolve_continuity(shot, legacy_mode=MODES[1], legacy_frames=22):
    mode = shot.get("continuity_mode", legacy_mode)
    if mode not in MODES:
        raise ValueError("Unknown shot continuity method.")
    video = int(shot.get("context_length", legacy_frames))
    if video not in GRID:
        raise ValueError("Video context must be 5, 22, 39 or 56 frames.")
    audio = int(shot.get("audio_context_length", video))
    if audio not in (0, *GRID):
        raise ValueError("Audio context must be off, 5, 22, 39 or 56 frames.")
    if shot.get("continuity") is False or shot.get("locked") or shot.get("source"):
        mode = MODES[0]
    if mode == MODES[0]:
        video = audio = 0
    elif mode == MODES[3]:
        video, audio = 1, 0
    return {"mode": mode, "video_frames": video, "audio_frames": min(audio, video)}
