"""Audio post-processing, seam de-clicking, and clip joining for MiniMax H3 Master Director."""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any, Dict, List

import torch


def fit_audio_duration(audio, frame_count, fps=24.0):
    """Keep decoded PCM exactly as long as the corresponding video frames."""
    wf = audio["waveform"]
    length = max(1, round(frame_count / fps * int(audio["sample_rate"])))
    wf = wf[..., :length]
    if wf.shape[-1] < length:
        padding = torch.zeros((*wf.shape[:-1], length - wf.shape[-1]), device=wf.device, dtype=wf.dtype)
        wf = torch.cat([wf, padding], dim=-1)
    return {**audio, "waveform": wf}


def slice_audio_frames(audio, start, end, fps=24):
    """Slice PCM using frame boundaries, keeping discarded context for the join."""
    rate = int(audio["sample_rate"])
    first, last = round(start / fps * rate), round(end / fps * rate)
    wave = audio["waveform"]
    out = fit_audio_duration({**audio, "waveform": wave[..., first:last]}, end-start, fps)
    out.update(frame_count=end-start, fps=fps)
    if start:
        out["seam_prefix"] = {"waveform": wave[..., :first], "sample_rate": rate}
    return out


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


def prepare_timeline_audio(audio_clips, fade_ms=15., enable_gain_match=True):
    """Join visible clip audio using discarded continuity prefixes, without
    shortening the timeline. Returns one independently encodable segment per clip.
    """
    if not math.isfinite(fade_ms) or fade_ms < 0:
        raise ValueError('Audio join fade must be a finite nonnegative number of milliseconds.')
    segments = []
    elapsed = Fraction(0)
    previous_boundary = 0
    for clip in audio_clips:
        prefix = clip.get('seam_prefix')
        context = None
        if (prefix and prefix['waveform'].shape[-1] and
                prefix.get('sample_rate') == clip.get('sample_rate') and
                prefix['waveform'].shape[:-1] == clip['waveform'].shape[:-1]):
            # Resample the continuous decode together. Resampling the discarded
            # prefix and visible audio separately introduces zero-padding/ringing
            # on both sides of the cut with the native sinc resampler.
            combined = {**clip, 'waveform':torch.cat([prefix['waveform'],clip['waveform']],-1)}
            prepared = concatenate_audio_clips([combined], crossfade_ms=0,
                enable_gain_match=False, enable_declick=False)['waveform']
            split = round(prefix['waveform'].shape[-1] * 48000 / int(clip['sample_rate']))
            context, wave = prepared[..., :split], prepared[..., split:]
        else:
            wave = concatenate_audio_clips([clip], crossfade_ms=0,
                enable_gain_match=False, enable_declick=False)['waveform']
        if 'frame_count' in clip:
            count, fps = int(clip['frame_count']), Fraction(str(clip.get('fps', 24)))
            if count < 1 or fps <= 0:
                raise ValueError('Timeline audio needs positive frame count and FPS.')
            elapsed += Fraction(count, 1) / fps
        else:
            elapsed += Fraction(int(wave.shape[-1]), 48000)
        boundary = round(elapsed * 48000)
        length = boundary - previous_boundary
        previous_boundary = boundary
        wave = wave[..., :length]
        if wave.shape[-1] < length:
            wave = torch.nn.functional.pad(wave, (0, length-wave.shape[-1]))
        gain = 1.
        if segments and enable_gain_match:
            gain = (torch.sqrt(torch.mean(segments[-1] ** 2) + 1e-8) /
                    torch.sqrt(torch.mean(wave ** 2) + 1e-8)).clamp(10**(-6/20), 10**(6/20))
            wave = wave * gain
        if segments and fade_ms > 0:
            previous = segments[-1]
            if prefix and prefix['waveform'].shape[-1]:
                if context is None:
                    context = concatenate_audio_clips([prefix], crossfade_ms=0,
                        enable_gain_match=False, enable_declick=False)['waveform']
                context = context * gain
                n = min(round(fade_ms / 1000 * 48000), previous.shape[-1], context.shape[-1])
                if n:
                    # The discarded prefix ends exactly where visible audio begins.
                    # Blend before the cut, leaving all video/sample timings intact.
                    ramp = .5 * (1-torch.cos(torch.linspace(0, math.pi, n)))
                    previous = previous.clone()
                    previous[..., -n:] = previous[..., -n:] * (1-ramp) + context[..., -n:] * ramp
                    segments[-1] = previous
            else:
                segments[-1] = apply_audio_fade(previous, 48000, 0, fade_ms)
                wave = apply_audio_fade(wave, 48000, fade_ms, 0)
        segments.append(wave)
    if segments and fade_ms > 0:
        segments[0] = apply_audio_fade(segments[0], 48000, fade_ms, 0)
        segments[-1] = apply_audio_fade(segments[-1], 48000, 0, fade_ms)
    return [{'waveform': wave, 'sample_rate': 48000} for wave in segments]


def join_timeline_audio(audio_clips, fade_ms=15., enable_gain_match=True):
    segments = prepare_timeline_audio(audio_clips, fade_ms, enable_gain_match)
    return {'waveform': torch.cat([a['waveform'] for a in segments], dim=-1),
            'sample_rate': 48000} if segments else {'waveform': torch.zeros((1, 2, 48000)), 'sample_rate': 48000}


def concatenate_audio_clips(
    audio_clips: List[Dict[str, Any]],
    target_sample_rate: int = 48000,
    crossfade_ms: float = 20.0,
    enable_gain_match: bool = True,
    enable_declick: bool = True,
    seam_fade_ms: float = 15.0,
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
        wf = wf.detach().cpu().float() if hasattr(wf, "detach") else wf.cpu().float()
        sr = int(clip.get("sample_rate", target_sample_rate))

        # Flatten batch dimension if present
        if wf.ndim == 3 and wf.shape[0] == 1:
            wf = wf.squeeze(0)  # [channels, samples]
        elif wf.ndim == 1:
            wf = wf.unsqueeze(0).repeat(2, 1)  # Mono to stereo

        if wf.shape[0] == 1:
            wf = wf.repeat(2, 1)  # Expand mono to stereo
        elif wf.shape[0] > 2:
            wf = wf[:2, :]  # Standardize multichannel to stereo

        # Resample if sample rate mismatches
        if sr > 1000 and sr != target_sample_rate:
            try:
                import torchaudio.transforms as T
                resampler = T.Resample(orig_freq=sr, new_freq=target_sample_rate)
                wf = resampler(wf)
            except Exception:
                # High quality linear interpolation fallback
                orig_samples = wf.shape[-1]
                target_samples = int(round(orig_samples * target_sample_rate / sr))
                if 0 < target_samples <= orig_samples * 10:
                    wf = torch.nn.functional.interpolate(wf.unsqueeze(0), size=target_samples, mode="linear", align_corners=False).squeeze(0)

        # Gain matching against previous clip
        if enable_gain_match and i > 0 and len(processed_waveforms) > 0:
            wf = match_audio_rms(wf, processed_waveforms[-1])

        # De-click boundary ramps
        if enable_declick:
            fade_ms = crossfade_ms if crossfade_ms > 0 else seam_fade_ms
            wf = apply_audio_fade(wf, target_sample_rate, fade_in_ms=fade_ms, fade_out_ms=fade_ms)

        processed_waveforms.append(wf)

    # Crossfade concatenation
    crossfade_samples = int(round((crossfade_ms / 1000.0) * target_sample_rate))
    min_clip_samples = min(w.shape[-1] for w in processed_waveforms)
    crossfade_samples = min(crossfade_samples, max(0, min_clip_samples // 2))

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
