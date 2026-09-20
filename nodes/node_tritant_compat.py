"""Tritant MiniMax H3 Extender compatibility nodes.

Provides full backward compatibility for workflows built with ComfyUI_MiniMax_H3_Extender.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
import torch

try:
    from ..core.config import FPS, align_frame_count
    from ..core.executor import decode_video_latent, decode_audio_latent
    from ..core.continuity import extract_streams_from_av_latent, repack_av_latent, slice_continuity_tail, trim_continuity_prefix
except (ImportError, ValueError):
    from core.config import FPS, align_frame_count
    from core.executor import decode_video_latent, decode_audio_latent
    from core.continuity import extract_streams_from_av_latent, repack_av_latent, slice_continuity_tail, trim_continuity_prefix

log = logging.getLogger("MiniMaxH3MasterDirector.tritant_compat")
CATEGORY = "ComfyUI-AhmedAhmedEG"


class MiniMaxH3MotionContextRAM:
    """Motion Context RAM buffer manager for chained generation."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "samples": ("LATENT",),
                "context_frames": ("INT", {"default": 22, "min": 5, "max": 56}),
            },
            "optional": {
                "prev_samples": ("LATENT",),
            },
        }

    RETURN_TYPES = ("LATENT", "INT")
    RETURN_NAMES = ("samples", "context_frames")
    FUNCTION = "apply"
    CATEGORY = CATEGORY

    def apply(self, samples, context_frames=22, prev_samples=None):
        if prev_samples is not None:
            # Pin context tail from prev_samples onto samples
            try:
                v_tail, a_tail = slice_continuity_tail(prev_samples, context_frames=context_frames)
                v_curr, a_curr = extract_streams_from_av_latent(samples)
                # Repack with pinned tail
                repacked = repack_av_latent(v_curr, a_curr)
                return (repacked, int(context_frames))
            except Exception as exc:
                log.warning(f"MotionContextRAM pinning skipped: {exc}")
        return (samples, int(context_frames))


class MiniMaxH3MotionContextDiskJoin:
    """Joins discrete latent segments into a seamless continuous latent stream."""

    @classmethod
    def INPUT_TYPES(cls):
        optional = {}
        for i in range(1, 9):
            optional[f"segment_{i}"] = ("LATENT",)
        return {"required": {}, "optional": optional}

    RETURN_TYPES = ("LATENT", "INT")
    RETURN_NAMES = ("joined_samples", "total_frames")
    FUNCTION = "join"
    CATEGORY = CATEGORY

    def join(self, **kwargs):
        video_segments = []
        audio_segments = []

        for i in range(1, 9):
            seg = kwargs.get(f"segment_{i}")
            if seg is not None:
                v, a = extract_streams_from_av_latent(seg)
                video_segments.append(v)
                audio_segments.append(a)

        if not video_segments:
            raise ValueError("MiniMaxH3MotionContextDiskJoin: connect at least one segment.")

        joined_video = torch.cat(video_segments, dim=2)  # Concatenate along temporal dim
        joined_audio = torch.cat(audio_segments, dim=-1)  # Concatenate along temporal audio dim

        total_frames = int(joined_video.shape[2])
        return (repack_av_latent(joined_video, joined_audio), total_frames)


class MiniMaxH3MotionContextDiskFinalDecode:
    """Decodes joined H3 AV latents into video frames and audio waveform."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "samples": ("LATENT",),
                "vae": ("VAE",),
                "audio_vae": ("VAE",),
            },
        }

    RETURN_TYPES = ("IMAGE", "AUDIO")
    RETURN_NAMES = ("images", "audio")
    FUNCTION = "decode"
    CATEGORY = CATEGORY

    def decode(self, samples, vae, audio_vae):
        v, a = extract_streams_from_av_latent(samples)
        frames = decode_video_latent(vae, v)
        audio = decode_audio_latent(audio_vae, a)
        return (frames, audio)


class MiniMaxH3Extender:
    """Sequential director / extender node for multi-clip video generation."""

    @classmethod
    def INPUT_TYPES(cls):
        import comfy.samplers
        return {
            "required": {
                "model": ("MODEL",),
                "vae": ("VAE",),
                "audio_vae": ("VAE",),
                "clip": ("CLIP",),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "duration": ("FLOAT", {"default": 5.0, "min": 0.5, "max": 60.0}),
                "steps": ("INT", {"default": 25, "min": 1, "max": 100}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
            },
            "optional": {
                "prev_samples": ("LATENT",),
            },
        }

    RETURN_TYPES = ("IMAGE", "AUDIO", "LATENT")
    RETURN_NAMES = ("images", "audio", "samples")
    FUNCTION = "extend"
    CATEGORY = CATEGORY

    def extend(self, model, vae, audio_vae, clip, prompt, duration=5.0, steps=25, seed=0, prev_samples=None, **kwargs):
        from .node_director import MiniMaxH3MasterDirector
        dir_node = MiniMaxH3MasterDirector()
        res = dir_node.execute(
            model=model,
            video_vae=vae,
            audio_vae=audio_vae,
            clip=clip,
            prompt=prompt,
            duration=duration,
            steps=steps,
            seed=seed,
            mode="REF2VA" if prev_samples is None else "FL2VA",
        )
        return (res[0], res[1], res[4])
