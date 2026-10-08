"""Director-owned MiniMax H3 segment motion/audio continuation helpers.

Pins the previous segment's tail into the next segment as never-denoised
conditioning, then trims that prefix from decoded output. Inspired by the
community Motion Context approach; original Apache-2.0 code for this Director.
"""


from __future__ import annotations


import logging


import torch


log = logging.getLogger("ComfyUI-MiniMaxH3-Director.h3_motion_context")


FPS = 24.0


AUDIO_HZ = 40.0


FRAME_RESCALE = 5.0 / 3.0


FRAME_PER_TOKEN = (1, 4, 4, 4, 4)


CONTEXT_FRAME_CHOICES = (5, 22, 39, 56)


DEFAULT_CONTEXT_FRAMES = 22


VIDEO_RUN_GRID = (124, 107, 90, 73, 56, 39, 22, 5, 1)


DEFAULT_AUDIO_CONTEXT_FRAMES = 24


def snap_context_frames(raw: int | float | None) -> int:
    """Snap UI/plan overlap to a supported context window (official baseline 22)."""
    try:
        n = int(raw or DEFAULT_CONTEXT_FRAMES)
    except (TypeError, ValueError):
        n = DEFAULT_CONTEXT_FRAMES
    chosen = min(CONTEXT_FRAME_CHOICES, key=lambda g: (abs(g - n), -g))
    return int(chosen)


def pixel_frames_for_latent_t(latent_t: int) -> int:
    return sum(FRAME_PER_TOKEN[k % 5] for k in range(int(latent_t)))


def steps_for_frames(n: int) -> int | None:
    k, covered = 0, 0
    while covered < n:
        covered += FRAME_PER_TOKEN[k % 5]
        k += 1
    return k if covered == n else None


def step_offsets(latent_t: int) -> list[int]:
    out, acc = [], 0
    for k in range(int(latent_t)):
        out.append(acc)
        acc += FRAME_PER_TOKEN[k % 5]
    return out


def _streams_from_latent(latent: dict) -> list[torch.Tensor]:
    samples = latent["samples"]
    # torch.Tensor.unbind splits the batch axis, not AV (video, audio) streams.
    if torch.is_tensor(samples):
        raise ValueError(
            "Director continuity: expected MiniMax H3 AV NestedTensor, "
            f"got packed tensor {tuple(samples.shape)}"
        )
    if hasattr(samples, "unbind"):
        parts = list(samples.unbind())
    elif isinstance(samples, (tuple, list)):
        parts = list(samples)
    else:
        raise ValueError(
            f"Director continuity: expected MiniMax H3 AV NestedTensor, got {type(samples)!r}"
        )
    if not parts:
        raise ValueError("Director continuity: AV latent has no streams")
    return parts


def _repack_av_streams(streams: list, template=None):
    """Rebuild H3 AV samples as NestedTensor. Do not pack_latents — that flattens."""
    tpl = template.get("samples") if isinstance(template, dict) else template
    try:
        import comfy.nested_tensor

        return comfy.nested_tensor.NestedTensor(tuple(streams))
    except Exception:
        pass
    cls = type(tpl) if tpl is not None and not torch.is_tensor(tpl) else None
    if cls is not None:
        try:
            return cls(tuple(streams))
        except Exception:
            pass
    raise ValueError("Director continuity: could not pack AV streams as NestedTensor.")


def video_from_latent(latent: dict) -> torch.Tensor:
    video = _streams_from_latent(latent)[0]
    if video.ndim == 4:
        video = video.unsqueeze(0)
    if video.ndim != 5:
        raise ValueError(
            f"Director continuity: expected video latent [B,C,T,H,W], got {tuple(video.shape)}"
        )
    return video


def av_pixel_size(latent: dict | None) -> tuple[int, int] | None:
    """Video canvas in pixels, or None if ``latent`` is not an H3 AV dict."""
    if not isinstance(latent, dict) or "samples" not in latent:
        return None
    try:
        video = video_from_latent(latent)
    except Exception:
        return None
    return int(video.shape[4]) * 16, int(video.shape[3]) * 16


def _resize_frames(image: torch.Tensor, width: int, height: int) -> torch.Tensor:
    import comfy.utils

    samples = image[..., :3].movedim(-1, 1)
    samples = comfy.utils.common_upscale(samples, width, height, "lanczos", "disabled")
    return samples.movedim(1, -1)


def _phase_aligned_tail_start(
    total_steps: int, n_steps: int, end_frame: int | None
) -> tuple[int, int, int]:
    """Pick a 5-cycle-aligned step start whose pixel window ends at/before ``end_frame``.

    Returns ``(start_step, pin_end_px, gap_after_pin)``.

    When ``end_frame`` is None, use the absolute latent end (official Motion Context).
    Director passes the *exported* end so align() overshoot beyond the visible
    segment is never pinned into the next clip. ``gap_after_pin`` is how many
    exported frames sit *after* the pin window — those must be dropped from the
    previous export before concat, or the next clip's opening will echo them.
    """
    if n_steps > total_steps:
        raise ValueError(
            f"Director continuity: need {n_steps} latent steps, context has {total_steps}."
        )
    if end_frame is None:
        start = total_steps - n_steps
        if start % 5 != 0:
            raise RuntimeError(
                f"Director continuity: tail start cycle {start % 5} != 0; refusing shifted join."
            )
        pin_end = pixel_frames_for_latent_t(total_steps)
        return start, pin_end, 0

    end_limit = int(end_frame)
    best_start = None
    best_end_px = -1
    for start in range(0, total_steps - n_steps + 1, 5):
        start_px = pixel_frames_for_latent_t(start)
        end_px = start_px + pixel_frames_for_latent_t(n_steps)
        if end_px <= end_limit and end_px >= best_end_px:
            best_start = start
            best_end_px = end_px
    if best_start is None:
        raise RuntimeError(
            f"Director continuity: no phase-aligned {n_steps}-step window ending "
            f"at or before frame {end_limit}."
        )
    gap = max(0, end_limit - best_end_px)
    if gap > 0:
        log.info(
            "Director continuity: pin window ends %df before export end "
            "(phase align; export_end=%d, pin_end=%d) — prev export tail will be trimmed",
            gap,
            end_limit,
            best_end_px,
        )
    return best_start, best_end_px, gap


def _video_tail_blocks(
    latent: dict,
    n: int,
    *,
    end_frame: int | None = None,
) -> tuple[list[torch.Tensor], list[int], int, int, int]:
    """Return ``(blocks, offsets, covered, pin_end_px, gap_after_pin)``."""
    video = video_from_latent(latent)
    total = int(video.shape[2])
    steps = steps_for_frames(n)
    if steps is None:
        raise ValueError(
            f"Director continuity: {n} frames is not a whole number of latent steps "
            f"(use {', '.join(str(x) for x in CONTEXT_FRAME_CHOICES)})."
        )
    start, pin_end_px, gap = _phase_aligned_tail_start(total, steps, end_frame)
    covered = pixel_frames_for_latent_t(steps)
    if covered != n:
        raise RuntimeError(
            f"Director continuity: {steps} steps cover {covered} frames, expected {n}."
        )
    blocks = [video[:1, :, start + k : start + k + 1].clone() for k in range(steps)]
    return blocks, step_offsets(steps), covered, pin_end_px, gap


def copy_av_tail_into_prefix(
    target: dict,
    source: dict,
    n_frames: int,
    *,
    end_frame: int | None = None,
) -> dict:
    """Overwrite the target head with the source tail (same spatial size)."""
    n = int(n_frames)
    blocks, _offsets, _covered, _pin_end, _gap = _video_tail_blocks(
        source, n, end_frame=end_frame
    )
    streams = list(_streams_from_latent(target))
    video = streams[0]
    squeezed = False
    if video.ndim == 4:
        video = video.unsqueeze(0)
        squeezed = True
    if int(video.shape[2]) < len(blocks):
        raise ValueError(
            f"Director continuity: target has {int(video.shape[2])} steps, "
            f"need {len(blocks)} to paste a {n}-frame prefix."
        )
    ref = blocks[0]
    if ref.ndim == 4:
        ref = ref.unsqueeze(0)
    if tuple(video.shape[3:]) != tuple(ref.shape[3:]) or int(video.shape[1]) != int(
        ref.shape[1]
    ):
        raise ValueError(
            "Director continuity: cannot paste prefix — spatial/channel mismatch "
            f"(target {tuple(video.shape)} vs source block {tuple(ref.shape)})."
        )
    video = video.clone()
    for k, blk in enumerate(blocks):
        piece = blk
        if piece.ndim == 4:
            piece = piece.unsqueeze(0)
        video[:, :, k : k + 1] = piece.to(device=video.device, dtype=video.dtype)
    if squeezed:
        video = video.squeeze(0)
    streams[0] = video.contiguous()
    out = dict(target)
    out.pop("noise_mask", None)
    try:
        out["samples"] = _repack_av_streams(streams, target)
    except Exception as exc:
        raise ValueError(
            f"Director continuity: could not pack prefix overwrite ({exc})."
        ) from exc
    log.info(
        "Director continuity: pasted %d-frame tail into current prefix (%d steps).",
        n,
        len(blocks),
    )
    return out


def _audio_tail_from_latent(
    latent: dict,
    a_frames: int,
    *,
    end_frame: int | None = None,
) -> tuple[torch.Tensor, int, float]:
    parts = _streams_from_latent(latent)
    if len(parts) < 2:
        raise ValueError("Director continuity: context latent has no audio stream.")
    video, audio = parts[0], parts[1]
    if video.ndim == 4:
        video = video.unsqueeze(0)
    if audio.ndim == 3:
        audio = audio.unsqueeze(0)
    if audio.ndim != 4:
        raise ValueError(
            f"Director continuity: expected audio latent [B,C,2,T], got {tuple(audio.shape)}"
        )
    total_t = int(audio.shape[-1])
    frames = pixel_frames_for_latent_t(int(video.shape[2]))
    overhang = total_t - FRAME_RESCALE * frames
    if not (0.0 <= overhang < 1.0):
        log.warning(
            "Director continuity: unexpected audio grid (%d steps / %d frames); "
            "assuming no overhang.",
            total_t,
            frames,
        )
        overhang = 0.0
    rt = int(round(a_frames / float(FPS) * AUDIO_HZ))
    if rt > total_t:
        log.warning(
            "Director continuity: asked for %d audio steps, latent has %d; pinning all.",
            rt,
            total_t,
        )
        rt = total_t
    if rt < 1:
        raise ValueError("Director continuity: empty audio window")
    if end_frame is None:
        audio_end = total_t
    else:
        # Match the video pin window end (export end), not the sample overshoot.
        audio_end = int(round(float(end_frame) / float(FPS) * AUDIO_HZ))
        audio_end = max(rt, min(total_t, audio_end))
    audio_start = audio_end - rt
    if audio_start < 0:
        audio_start = 0
        rt = audio_end
    return audio[:1, ..., audio_start:audio_end].clone(), rt, float(overhang)


def _usable_context_audio(audio: dict | None) -> dict | None:
    """Return ``audio`` only when it has a non-empty waveform (resample-safe)."""
    if not isinstance(audio, dict):
        return None
    waveform = audio.get("waveform")
    if not isinstance(waveform, torch.Tensor) or waveform.numel() <= 0:
        return None
    if waveform.ndim < 1 or int(waveform.shape[-1]) <= 0:
        return None
    return audio


def _encode_tail_audio(audio_vae, audio: dict, seconds: float) -> tuple[torch.Tensor, int]:
    try:
        import torchaudio
    except ImportError:
        torchaudio = None
    usable = _usable_context_audio(audio)
    if usable is None:
        raise ValueError("Director continuity: empty context audio waveform")
    waveform = usable["waveform"]
    sr = int(usable.get("sample_rate") or getattr(audio_vae, "audio_sample_rate", 32000) or 32000)
    vae_sr = int(getattr(audio_vae, "audio_sample_rate", 32000))
    if sr != vae_sr:
        if torchaudio is None:
            from torch.nn import functional as F
            waveform = F.interpolate(waveform.float(), size=max(1, round(waveform.shape[-1]*vae_sr/sr)), mode="linear", align_corners=False)
        else:
            waveform = torchaudio.functional.resample(waveform, sr, vae_sr)
    want = int(round(seconds * vae_sr))
    have = int(waveform.shape[-1])
    if have >= want:
        waveform = waveform[..., have - want :]
    z = audio_vae.encode(waveform[:1].movedim(1, -1))
    return z, int(z.shape[-1])
