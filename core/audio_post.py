"""Audio post-processing, seam de-clicking, and clip joining for MiniMax H3 Master Director."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np
import torch


def apply_audio_fade(
    waveform: torch.Tensor,
    sample_rate: int,
    fade_in_ms: float = 15.0,
    fade_out_ms: float = 25.0,
) -> torch.Tensor:
    """Apply gentle cosine fade-in and fade-out ramps to eliminate pops and clicks at seams."""
    out = waveform.clone()
    channels, num_samples = out.shape[-2], out.shape[-1]
    
    # Fade in
    fade_in_len = min(num_samples // 2, int(round((fade_in_ms / 1000.0) * sample_rate)))
    if fade_in_len > 0:
        ramp_in = 0.5 * (1.0 - torch.cos(torch.linspace(0, math.pi, fade_in_len, device=out.device)))
        out[..., :fade_in_len] *= ramp_in

    # Fade out
    fade_out_len = min(num_samples // 2, int(round((fade_out_ms / 1000.0) * sample_rate)))
    if fade_out_len > 0:
        ramp_out = 0.5 * (1.0 + torch.cos(torch.linspace(0, math.pi, fade_out_len, device=out.device)))
        out[..., -fade_out_len:] *= ramp_out

    return out


def match_audio_rms(
    target_waveform: torch.Tensor,
    reference_waveform: torch.Tensor,
    max_gain_db: float = 6.0,
) -> torch.Tensor:
    """Level-match target waveform to reference waveform using RMS gain clamping."""
    ref_rms = torch.sqrt(torch.mean(reference_waveform ** 2) + 1e-8)
    tgt_rms = torch.sqrt(torch.mean(target_waveform ** 2) + 1e-8)

    ratio = (ref_rms / tgt_rms).item()
    max_gain = 10.0 ** (max_gain_db / 20.0)
    min_gain = 10.0 ** (-max_gain_db / 20.0)
    gain = max(min_gain, min(max_gain, ratio))

    return target_waveform * gain


def concatenate_audio_clips(
    audio_clips: List[Dict[str, Any]],
    target_sample_rate: int = 48000,
    crossfade_ms: float = 20.0,
    enable_gain_match: bool = True,
    enable_declick: bool = True,
) -> Dict[str, Any]:
    """Assemble multiple audio clips into one seamless, continuous PCM track."""
    valid_clips = [c for c in audio_clips if c and "waveform" in c and c["waveform"].numel() > 0]
    if not valid_clips:
        # 1-second silence fallback
        silence = torch.zeros((1, 2, target_sample_rate), dtype=torch.float32)
        return {"waveform": silence, "sample_rate": target_sample_rate}

    processed_waveforms: List[torch.Tensor] = []

    for i, clip in enumerate(valid_clips):
        wf = clip["waveform"]
        sr = int(clip.get("sample_rate", target_sample_rate))

        # Flatten batch dimension if present
        if wf.ndim == 3 and wf.shape[0] == 1:
            wf = wf.squeeze(0)  # [channels, samples]
        elif wf.ndim == 1:
            wf = wf.unsqueeze(0).repeat(2, 1)  # Mono to stereo

        if wf.shape[0] == 1:
            wf = wf.repeat(2, 1)  # Expand to stereo

        # Resample if sample rate mismatches
        if sr != target_sample_rate:
            import torchaudio.transforms as T
            resampler = T.Resample(orig_freq=sr, new_freq=target_sample_rate)
            wf = resampler(wf)

        # Gain matching against previous clip
        if enable_gain_match and i > 0 and len(processed_waveforms) > 0:
            wf = match_audio_rms(wf, processed_waveforms[-1])

        # De-click boundary ramps
        if enable_declick:
            wf = apply_audio_fade(wf, target_sample_rate, fade_in_ms=crossfade_ms, fade_out_ms=crossfade_ms)

        processed_waveforms.append(wf)

    # Crossfade concatenation
    crossfade_samples = int(round((crossfade_ms / 1000.0) * target_sample_rate))
    total_len = sum(w.shape[-1] for w in processed_waveforms)
    if len(processed_waveforms) > 1 and crossfade_samples > 0:
        total_len -= (len(processed_waveforms) - 1) * crossfade_samples

    channels = processed_waveforms[0].shape[0]
    assembled = torch.zeros((channels, max(1, total_len)), dtype=torch.float32)
    
    current_idx = 0
    for i, w in enumerate(processed_waveforms):
        w_len = w.shape[-1]
        if i == 0 or crossfade_samples <= 0:
            assembled[:, current_idx : current_idx + w_len] = w
            current_idx += w_len
        else:
            # Overlap-add with crossfade
            overlap_start = current_idx - crossfade_samples
            assembled[:, overlap_start : overlap_start + crossfade_samples] += w[:, :crossfade_samples]
            assembled[:, current_idx : current_idx + (w_len - crossfade_samples)] = w[:, crossfade_samples:]
            current_idx += w_len - crossfade_samples

    # Clamping peak to [-1.0, 1.0] to prevent clipping distortion
    peak = torch.max(torch.abs(assembled))
    if peak > 1.0:
        assembled = assembled / peak

    return {"waveform": assembled.unsqueeze(0), "sample_rate": target_sample_rate}
