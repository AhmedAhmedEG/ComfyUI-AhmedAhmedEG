"""Plain masked continuation, mirroring H3 Continuity Studio (MIT, KadoBOT/ComfyUI-H3-Continuity-Studio).

Studio's `latents.build_continuation`: the previous clip's saved latent supplies its
last `context_frames` frames (its final tokens), written unchanged at the start of the
new latent and frozen with noise mask 0; the matching audio ticks are frozen too. No
per-step remask and no grading of the carried latent. A continuing clip adds 17k new
frames, and the previous clip's last frame guides the first new frame (Studio's
`continuation_guide`, on by default).
"""
from __future__ import annotations

import torch

FPS = 24
AUDIO_TICKS_PER_SECOND = 40
FRAME_PER_TOKEN = (1, 4, 4, 4, 4)
GRID = 17


def frames_for_tokens(tokens):
    return sum(FRAME_PER_TOKEN[k % 5] for k in range(int(tokens)))


def tokens_for_frames(frames):
    if frames < 5 or frames % 17 != 5:
        raise ValueError(f"{frames} frames is not on the H3 17k+5 frame grid")
    return (frames - 5) // 17 * 5 + 2


def ticks_for_frames(frames):
    return round(frames * AUDIO_TICKS_PER_SECOND / FPS)


def continuing_budget(requested_frames, context_frames):
    """(sampled frames, new frames): Studio snaps a continuing clip to 17k new frames, k >= 1."""
    new = GRID * max(1, round(int(requested_frames) / GRID))
    return int(context_frames) + new, new


def audio_context_window(source_frames, source_ticks, context_frames):
    """(source start, target start, ticks) with audio following the video context (Studio default)."""
    full = ticks_for_frames(context_frames)
    if source_ticks < full:
        raise ValueError(f"the previous clip has only {source_ticks} audio ticks, fewer than the aligned {full}")
    start = round((source_frames - context_frames) * AUDIO_TICKS_PER_SECOND / FPS)
    start = max(0, min(start, source_ticks - full))
    return start, 0, full


def _streams(latent):
    samples = latent["samples"]
    tensors = samples.tensors if hasattr(samples, "tensors") else (list(samples.unbind()) if hasattr(samples, "unbind") and not torch.is_tensor(samples) else samples)
    video, audio = tensors[0], tensors[1]
    if video.ndim != 5 or audio.ndim not in (3, 4):
        raise ValueError("Pure carry expects a MiniMax H3 audio+video latent")
    return video, audio


def _nested(video, audio):
    try:
        from comfy.nested_tensor import NestedTensor
        return NestedTensor((video, audio))
    except Exception:
        return (video, audio)


def build_continuation(latent, previous, context_frames, carry_audio=True):
    """Write the previous clip's last `context_frames` frames into `latent` and freeze them."""
    if "noise_mask" in latent:
        raise ValueError("Pure carry: the latent already has a noise mask")
    video, audio = _streams(latent)
    source_video, source_audio = _streams(previous)
    if tuple(source_video.shape[3:]) != tuple(video.shape[3:]):
        raise ValueError("Pure carry: the previous clip has a different resolution")
    source_frames = frames_for_tokens(source_video.shape[2])
    frames = frames_for_tokens(video.shape[2])
    if context_frames > source_frames:
        raise ValueError(f"Pure carry: {context_frames} carried frames is longer than the previous clip ({source_frames})")
    if context_frames >= frames:
        raise ValueError(f"Pure carry: this clip has {frames} frames; it must be longer than {context_frames}")
    tokens = tokens_for_frames(context_frames)
    carried_video = source_video[:1, :, -tokens:].to(device=video.device, dtype=video.dtype)
    video = video.clone()
    video[:, :, :tokens] = carried_video
    video_mask = torch.ones((1, 1) + tuple(video.shape[2:]), device=video.device)
    video_mask[:, :, :tokens] = 0
    audio_mask = torch.ones((1, 1) + tuple(audio.shape[2:]), device=audio.device)
    ticks = 0
    if carry_audio:
        start, target, ticks = audio_context_window(source_frames, int(source_audio.shape[-1]), context_frames)
        if audio.shape[-1] < target + ticks:
            raise ValueError("Pure carry: this clip has too few audio ticks to carry")
        carried_audio = source_audio[:1, ..., start:start + ticks].to(device=audio.device, dtype=audio.dtype)
        if carried_audio.shape[-1] != ticks:
            raise ValueError("Pure carry: the previous clip has too few audio ticks")
        audio = audio.clone()
        audio[..., target:target + ticks] = carried_audio
        audio_mask[..., target:target + ticks] = 0
    out = dict(latent)
    out["samples"] = _nested(video, audio)
    out["noise_mask"] = _nested(video_mask, audio_mask)
    return out, tokens, ticks
