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


def latent_sharpness(video: torch.Tensor) -> float:
    """High-frequency energy of a video latent [B,C,T,H,W], relative to its spread."""
    v = video.detach().float()
    grad = (v[..., 1:, :] - v[..., :-1, :]).abs().mean() + (v[..., :, 1:] - v[..., :, :-1]).abs().mean()
    return float(grad / v.std().clamp_min(1e-6))


def _soften(video: torch.Tensor) -> torch.Tensor:
    # 3x3 spatial smoothing per channel and latent frame.
    import torch.nn.functional as F
    b, c, t, h, w = video.shape
    flat = video.permute(0, 2, 1, 3, 4).reshape(b * t, c, h, w)
    flat = F.avg_pool2d(F.pad(flat, (1, 1, 1, 1), mode="replicate"), 3, stride=1)
    return flat.reshape(b, t, c, h, w).permute(0, 2, 1, 3, 4)


CARRY_SHARPNESS_TOLERANCE = 1.02
CARRY_MAX_SOFTEN = 0.6


def guard_carried_sharpness(latent_dict: Dict[str, Any], baseline: float, tail_tokens: int = 12):
    """Stop grain/sharpness from ratcheting up along a continuity chain.

    A clip ends a little sharper than it starts; the next clip continues from
    that ending and adds its own rise, so it compounds hop after hop. Only the
    copy that is carried into the next clip is touched: if its tail is sharper
    than the chain's baseline, blend in just enough smoothing to return it to
    the baseline (capped). Delivered clips and audio are unchanged.
    Returns (latent_dict_for_carry, applied_amount).
    """
    if latent_dict is None or not baseline or baseline <= 0:
        return latent_dict, 0.0
    samples = latent_dict.get("samples")
    streams, nested = unpack_av_samples(samples)
    video = streams[0]
    if video.ndim != 5:
        return latent_dict, 0.0
    v = video.float()
    tail = v[:, :, -min(int(tail_tokens), v.shape[2]):]
    target = float(baseline) * CARRY_SHARPNESS_TOLERANCE
    if latent_sharpness(tail) <= target:
        return latent_dict, 0.0
    smooth_tail = _soften(tail)
    lo, hi = 0.0, CARRY_MAX_SOFTEN
    for _ in range(14):  # smallest amount that reaches the baseline
        mid = (lo + hi) / 2
        if latent_sharpness(tail + mid * (smooth_tail - tail)) > target:
            lo = mid
        else:
            hi = mid
    amount = hi
    streams[0] = (v + amount * (_soften(v) - v)).to(video.dtype)
    out = dict(latent_dict)
    if not nested:
        out["samples"] = streams[0]
    elif isinstance(samples, (tuple, list)):
        out["samples"] = type(samples)(streams)
    else:
        out["samples"] = type(samples)(tuple(streams))
    return out, amount


SEAM_BIAS_MAX_SCALE = 0.15


def align_to_continued_context(latent_dict: Dict[str, Any], guide_video: torch.Tensor):
    """Remove the per-hop render bias of a continued clip.

    The first tokens of a continued clip re-render the same moment as the
    previous clip's tail tokens (``guide_video``). H3 renders guided frames a few
    percent more contrasty with a small colour offset; the rest of the clip
    continues from that, so the bias compounded hop after hop. The difference on
    this identical content is pure bias: estimate it per channel (skipping the
    special first latent frame) and remove it from the whole clip.
    Returns (latent_dict, contrast_ratio_removed).
    """
    if latent_dict is None or guide_video is None:
        return latent_dict, 1.0
    samples = latent_dict.get("samples")
    streams, nested = unpack_av_samples(samples)
    video = streams[0]
    guide = guide_video.float().to(video.device)
    if video.ndim != 5 or guide.ndim != 5 or guide.shape[1] != video.shape[1] or guide.shape[3:] != video.shape[3:]:
        return latent_dict, 1.0
    n = min(int(guide.shape[2]), int(video.shape[2]) - 1)
    if n < 3:
        return latent_dict, 1.0
    v = video.float()
    rendered, target = v[:, :, 1:n], guide[:, :, 1:n]
    axes = (0, 2, 3, 4)
    r_mean, r_std = rendered.mean(dim=axes), rendered.std(dim=axes).clamp_min(1e-6)
    t_mean, t_std = target.mean(dim=axes), target.std(dim=axes)
    scale = (t_std / r_std).clamp(1 - SEAM_BIAS_MAX_SCALE, 1 + SEAM_BIAS_MAX_SCALE)
    shift = t_mean - scale * r_mean
    view = [1, -1, 1, 1, 1]
    streams[0] = (v * scale.view(view) + shift.view(view)).to(video.dtype)
    out = dict(latent_dict)
    if not nested:
        out["samples"] = streams[0]
    elif isinstance(samples, (tuple, list)):
        out["samples"] = type(samples)(streams)
    else:
        out["samples"] = type(samples)(tuple(streams))
    return out, float(1.0 / scale.median())


def match_color_temperature_and_grade(
    current_frames: torch.Tensor,
    prev_tail_frames: torch.Tensor,
    blend_window: int = 12,
    inplace: bool = False,
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

    out = current_frames if inplace and current_frames.dtype == torch.float32 else current_frames.clone().float()
    window = min(blend_window, out.shape[0])

    # Linear falloff ramp from gain -> 1.0
    ramp = torch.linspace(1.0, 0.0, steps=window, device=out.device).view(-1, 1, 1, 1)
    gain_tensor = gain.to(out.device).view(1, 1, 1, -1)

    # Blend correction into the opening frames
    out[:window] = out[:window] * (1.0 + ramp * (gain_tensor - 1.0))
    return out.clamp_(0.0, 1.0)


# Per-shot continuity policy, with legacy global configuration fallback.
MODES = ("Independent (No Continuity)", "Motion Context (Chained)",
         "Latent Carry (Pinned)", "FL2VA Tail Handoff")
GRID = (5, 22, 39, 56)
AUDIO_GRID = (0, 5, 22, 24, 39, 56)


def resolve_continuity(shot, legacy_mode=MODES[1], legacy_frames=22):
    mode = shot.get("continuity_mode", legacy_mode)
    if mode not in MODES:
        raise ValueError("Unknown shot continuity method.")
    video = int(shot.get("context_length", legacy_frames))
    if video not in GRID:
        raise ValueError("Video context must be 5, 22, 39 or 56 frames.")
    audio = int(shot.get("audio_context_length", video))
    if audio not in AUDIO_GRID:
        raise ValueError("Audio context must be off, 5, 22, 24, 39 or 56 frames.")
    duration_policy = shot.get("continuity_duration_policy", "new")
    if duration_policy not in ("new", "total"):
        raise ValueError("Continuity duration policy must be new or total.")
    if shot.get("continuity") is False or shot.get("locked") or shot.get("source"):
        mode = MODES[0]
    if mode == MODES[0]:
        video = audio = 0
    elif mode == MODES[3]:
        video, audio = 1, 0
    return {"mode": mode, "video_frames": video, "audio_frames": audio,
            "duration_policy": duration_policy}


def dependent_successors(clips, changed_index, legacy_mode=MODES[1], legacy_frames=22, *, preserve_approved=False):
    """The contiguous dependency chain; an independent/source clip breaks it."""
    result = []
    for shot in clips[changed_index + 1:]:
        if preserve_approved and shot.get('validated') and not shot.get('pending_upstream'):
            break  # An approved saved take is a stable boundary during execution.
        # A take kept only until its upstream clip is regenerated
        # ("pending_upstream") is not a boundary: it depends on the old take.
        if str(shot.get('type', '')).upper() == 'VIDEO':
            break
        policy = resolve_continuity(shot, legacy_mode, legacy_frames)
        tail = float(shot.get('tail_seconds', float(shot.get('tail_frames', 12)) / FPS))
        if policy['mode'] == MODES[0] or tail <= 0:
            break
        result.append(str(shot['id']))
    return result


def continuity_frame_budget(visible_frames, context_frames, policy="new"):
    """Return (sample frames, visible frames); old workflows retain new-time policy."""
    from .config import align_frame_count
    requested = align_frame_count(int(visible_frames))
    if policy == "total":
        if context_frames >= requested:
            raise ValueError("Continuity context must be shorter than the requested total duration.")
        return requested, requested - context_frames
    if policy != "new":
        raise ValueError("Unknown continuity duration policy.")
    return align_frame_count(requested + context_frames), requested
