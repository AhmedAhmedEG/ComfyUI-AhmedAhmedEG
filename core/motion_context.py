"""Native sampled-latent temporal guides; no global patches or sample prefix mask."""
from __future__ import annotations

import logging
from .continuity import extract_streams_from_av_latent
from .vendor.aimixer.director.h3_motion_context import (
    _video_tail_blocks, pixel_frames_for_latent_t, step_offsets,
    _resize_frames, _encode_tail_audio, _usable_context_audio,
)

log = logging.getLogger(__name__)


def apply_motion_context(positive, target, *, previous_av, previous_tail, vae,
                         audio_vae, context_frames, audio_frames,
                         context_end_frame=None):
    """Return (conditioning, prefix frames, predecessor trim, source kind).

    Compatible cached AV tails become native guide rows directly. Pixel fallback
    is explicit, for imported footage or a changed canvas. Existing refs and
    interior/closing guides remain on every conditioning entry.
    """
    video, _ = extract_streams_from_av_latent(target)
    source_video = source_audio = None
    if previous_av is not None:
        source_video, source_audio = extract_streams_from_av_latent(previous_av)
        if source_audio.ndim == 3:
            source_audio = source_audio.unsqueeze(0)
    compatible = source_video is not None and tuple(source_video.shape[:2]) == tuple(video.shape[:2]) and tuple(source_video.shape[3:]) == tuple(video.shape[3:])
    previous_trim = 0
    if compatible:
        blocks, offsets, span, pin_end, previous_trim = _video_tail_blocks(
            previous_av, context_frames, end_frame=context_end_frame)
        kind = "sampled_latent"
    else:
        frames = previous_tail.get("tail_frames")
        if frames is None or int(frames.shape[0]) < context_frames:
            raise ValueError("Motion Context needs a compatible AV latent or enough decoded tail frames.")
        tail = frames[-context_frames:]
        width, height = int(video.shape[4])*16, int(video.shape[3])*16
        if tuple(tail.shape[1:3]) != (height, width):
            tail = _resize_frames(tail, width, height)
        encoded = vae.encode(tail[..., :3])
        span = pixel_frames_for_latent_t(int(encoded.shape[2]))
        if span != context_frames:
            raise ValueError("Motion Context pixel fallback does not match the H3 context grid.")
        blocks = [encoded[:, :, k:k+1].clone() for k in range(encoded.shape[2])]
        offsets = step_offsets(len(blocks))
        pin_end = None
        kind = "decoded_fallback"
        log.info("Motion Context: using decoded tail fallback (no compatible sampled latent).")

    guides = []
    for offset, block in zip(offsets, blocks):
        # Native targets pad to a 2x2 DiT patch grid; guide blocks need it too.
        pad_h, pad_w = int(video.shape[3]) % 2, int(video.shape[4]) % 2
        if pad_h or pad_w:
            import torch.nn.functional as F
            block = F.pad(block, (0, pad_w, 0, pad_h))
        guides.append({"resolved_frame_index": offset, "latent": block})

    if audio_frames:
        if compatible:
            # Audio runs at 40 Hz. Keep the signed phase of the actual source
            # boundary; independent context lengths align by their END.
            source_count = pixel_frames_for_latent_t(int(source_video.shape[2]))
            end = min(int(source_audio.shape[-1]), round(pin_end * 40 / 24))
            ticks = min(end, round(audio_frames * 40 / 24))
            audio = source_audio[:1, ..., end-ticks:end].clone()
            phase = end - pin_end * 40 / 24
            if context_end_frame is None and pin_end == source_count:
                phase = int(source_audio.shape[-1]) - source_count * 40 / 24
            if not -.5 < phase < .5:
                log.warning("Motion Context: source audio has a nonnative boundary; using zero phase residual.")
                phase = 0.
        else:
            sound = _usable_context_audio(previous_tail.get("tail_audio"))
            if sound is None:
                audio = None
            else:
                audio, ticks = _encode_tail_audio(audio_vae, sound, audio_frames / 24)
                phase = 0.
        if audio is not None and int(audio.shape[-1]):
            # Quantize the GUIDE END on H3's 40 Hz grid before deriving its
            # start, matching the original Extender's native-guide contract.
            end_tick = round(span * 40 / 24 + phase)
            guides.append({"resolved_frame_index": (end_tick-ticks) * 24 / 40,
                           "audio_latent": audio})

    out = []
    for embedding, metadata, *extra in positive:
        copied = dict(metadata)
        copied["minimax_keyframes"] = [*guides, *metadata.get("minimax_keyframes", [])]
        out.append([embedding, copied, *extra])
    log.info("Motion Context: %s, video=%df, audio=%df, prefix=%df, predecessor trim=%df",
             kind, span, audio_frames, span, previous_trim)
    return out, span, previous_trim, kind
