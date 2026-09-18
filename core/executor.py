"""Master execution engine uniting conditioning, multi-segment continuity, sampling, and export."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import torch

from .config import (
    FPS,
    AUDIO_SAMPLE_RATE,
    align_frame_count,
    video_latent_t,
    audio_latent_length,
)
from .task_modes import (
    MODE_T2VA,
    MODE_I2VA,
    MODE_FL2VA,
    MODE_L2VA,
    MODE_REF2VA,
    MODE_V2V,
    MODE_RV2V,
    MODE_INPAINT,
    normalize_mode,
)
from .media_io import load_image, load_video, load_audio, load_embedded_video_audio
from .refmod import process_refmod_rows, build_refmod_tag_map, translate_refmod_aliases
from .prompt_engine import (
    build_keyframe_mode_prompt,
    build_ref2va_prompt,
)
from .motion_context import ensure_motion_context_patches, CTX_FRAME_KEY
from .continuity import (
    slice_continuity_tail,
    trim_continuity_prefix,
    trim_continuity_audio_prefix,
    match_color_temperature_and_grade,
)
from .cache_manager import ProjectCacheManager, compute_clip_fingerprint
from .audio_post import concatenate_audio_clips

log = logging.getLogger("MiniMaxH3MasterDirector.executor")


def get_native_h3_node(class_name: str):
    """Dynamically resolve ComfyUI native MiniMax H3 nodes."""
    try:
        from comfy_extras import nodes_minimax_h3
        return getattr(nodes_minimax_h3, class_name)
    except Exception as exc:
        raise RuntimeError(
            f"MiniMax H3 Master Director requires ComfyUI's native {class_name} node. "
            "Please update ComfyUI to a version that includes official MiniMax H3 support."
        ) from exc


def decode_video_latent(vae, latent_tensor: torch.Tensor) -> torch.Tensor:
    """Decode a video latent tensor [1, C, T, H, W] to IMAGE batch [T, H, W, 3]."""
    images = vae.decode(latent_tensor)
    if images.ndim == 5:
        # [B, T, H, W, C] -> [B*T, H, W, C]
        b, t, h, w, c = images.shape
        images = images.reshape(b * t, h, w, c)
    return images.cpu()


def decode_audio_latent(audio_vae, audio_latent_tensor: torch.Tensor) -> Dict[str, Any]:
    """Decode an audio latent tensor to standard ComfyUI audio dict."""
    audio = audio_vae.decode(audio_latent_tensor).movedim(-1, 1)
    std = torch.std(audio, dim=[1, 2], keepdim=True) * 5.0
    std[std < 1.0] = 1.0
    audio = audio / std

    sr = getattr(audio_vae, "audio_sample_rate_output", getattr(audio_vae, "audio_sample_rate", 32000))
    return {"waveform": audio.cpu(), "sample_rate": int(sr)}


class MasterDirectorExecutor:
    """Orchestrates execution of the entire director pipeline."""

    def __init__(self, project_id: str = "default"):
        self.cache_mgr = ProjectCacheManager(project_id)
        ensure_motion_context_patches()

    def build_conditioning(
        self,
        mode: str,
        prompt: str,
        width: int,
        height: int,
        duration: float,
        clip,
        vae,
        audio_vae=None,
        first_frame=None,
        last_frame=None,
        guide_frames=None,
        ref_images: Optional[Dict[str, Any]] = None,
        ref_videos: Optional[Dict[str, Any]] = None,
        ref_video_audios: Optional[Dict[str, Any]] = None,
        ref_audios: Optional[Dict[str, Any]] = None,
        refmod_items: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[Any, Any, str]:
        """Generate positive conditioning and empty AV latent using official H3 native nodes."""
        canon = normalize_mode(mode)
        frame_count = align_frame_count(int(duration * FPS))

        if canon in (MODE_T2VA, MODE_I2VA, MODE_FL2VA, MODE_L2VA, MODE_INPAINT):
            node_cls = get_native_h3_node("MiniMaxH3ImageToVideo")
            ff = first_frame
            lf = last_frame
            fc = 5 if canon == MODE_INPAINT else frame_count

            positive, latent = node_cls.execute(
                clip=clip,
                vae=vae,
                prompt=prompt,
                width=width,
                height=height,
                length=fc,
                first_frame=ff,
                last_frame=lf,
            )

            # Inject dynamic intermediate image guides if present (MiniMaxH3AddGuide support)
            if guide_frames and canon == MODE_FL2VA:
                keyframes = list(positive[0][1].get("minimax_keyframes", []))
                for g in guide_frames:
                    g_img = g.get("frame")
                    g_idx = g.get("frame_idx", 0)
                    if g_img is not None:
                        import node_helpers
                        g_latent = vae.encode(g_img[:1])
                        keyframes.append({"resolved_frame_index": g_idx, "latent": g_latent})
                positive = [[emb, {**meta, "minimax_keyframes": keyframes}] for emb, meta in positive]

            return positive, latent, prompt

        # REF2VA / V2V / RV2V
        node_cls = get_native_h3_node("MiniMaxH3ReferenceToVideo")
        if audio_vae is None:
            raise ValueError("audio_vae is required for REF2VA mode.")

        # If RefMods are attached, encode them as reference items
        ref_clip = clip
        native_blocks = []
        if refmod_items:
            decoded_items = []
            for block in refmod_items:
                if block.get("kind") == "audio":
                    decoded_items.append({"type": "audio"})
                    native_blocks.append({"kind": "audio", "ref_audio_t": int(block.get("latent_t", 0)), "audio_latent": block["latent"]})
                    continue
                latent = block["latent"]
                pixels = vae.decode(latent)
                if getattr(pixels, "ndim", 0) == 5 and pixels.shape[0] == 1:
                    pixels = pixels[0]
                is_video = block["kind"] == "video" or (getattr(latent, "ndim", 0) >= 5 and latent.shape[2] > 1)
                decoded_items.append({"type": "image" if not is_video else "video", "data": pixels.cpu().clone()})
                if is_video:
                    native_blocks.append({"kind": block["kind"], "latent": latent, "latent_t": latent.shape[2], "latent_h": latent.shape[3], "latent_w": latent.shape[4], "ref_audio_t": 0, "audio_latent": None})
                else:
                    native_blocks.append({"kind": "image", "latent": latent, "latent_h": latent.shape[2], "latent_w": latent.shape[3]})

            class RefClipWrapper:
                def tokenize(self, text, **kwargs):
                    kwargs["minimax_ref_items"] = list(kwargs.get("minimax_ref_items") or []) + decoded_items
                    return clip.tokenize(text, **kwargs)
                def encode_from_tokens_scheduled(self, tokens):
                    return clip.encode_from_tokens_scheduled(tokens)
            ref_clip = RefClipWrapper()

        positive, latent = node_cls.execute(
            clip=ref_clip,
            prompt=prompt,
            width=width,
            height=height,
            length=frame_count,
            ref_image_size="match",
            vae=vae,
            audio_vae=audio_vae,
            ref_images=ref_images or {},
            ref_videos=ref_videos or {},
            ref_video_audios=ref_video_audios or {},
            ref_audios=ref_audios or {},
        )

        if native_blocks:
            positive = [[emb, {**meta, "minimax_refs": list(meta.get("minimax_refs", [])) + native_blocks}] for emb, meta in positive]

        return positive, latent, prompt
