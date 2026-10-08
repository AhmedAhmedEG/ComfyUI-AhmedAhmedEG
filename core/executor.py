"""Master execution engine uniting conditioning, multi-segment continuity, sampling, and export."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import torch

from .config import FPS, align_frame_count
from .task_modes import MODE_T2VA, MODE_I2VA, MODE_FL2VA, MODE_L2VA, MODE_INPAINT, normalize_mode
from .refmod import get_cached_visual_item, set_cached_visual_item, refmod_fingerprint
from .cache_manager import ProjectCacheManager
from .sampling import native_outputs

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
    audio = audio_vae.decode(audio_latent_tensor)
    if audio.ndim == 3 and audio.shape[-1] <= 2 and audio.shape[1] > 2:
        audio = audio.movedim(-1, 1)
    elif audio.ndim == 2:
        audio = audio.unsqueeze(0)
        if audio.shape[-1] <= 2 and audio.shape[1] > 2:
            audio = audio.movedim(-1, 1)

    std = torch.std(audio, dim=[1, 2], keepdim=True) * 5.0
    std[std < 1.0] = 1.0
    audio = audio / std

    sr = None
    if hasattr(audio_vae, "audio_sample_rate_output"):
        val = getattr(audio_vae, "audio_sample_rate_output")
        if isinstance(val, (int, float)) and val > 1000:
            sr = int(val)
    if sr is None and hasattr(audio_vae, "audio_sample_rate"):
        val = getattr(audio_vae, "audio_sample_rate")
        if isinstance(val, (int, float)) and val > 1000:
            sr = int(val)
    if sr is None or sr <= 1000:
        sr = 32000
    return {"waveform": audio.cpu(), "sample_rate": int(sr)}


class MasterDirectorExecutor:
    """Orchestrates execution of the entire director pipeline."""

    def __init__(self, project_id: str = "default"):
        self.cache_mgr = ProjectCacheManager(project_id)
        # Current native H3 supports interior guides and keyframe/reference coexistence.
        # Do not replace ComfyUI global methods while executing a node.

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

            positive, latent = native_outputs(node_cls.execute(
                clip=clip,
                vae=vae,
                prompt=prompt,
                width=width,
                height=height,
                length=fc,
                first_frame=ff,
                last_frame=lf,
            ))

            # Inject dynamic intermediate image guides if present (MiniMaxH3AddGuide support)
            if guide_frames:
                keyframes = list(positive[0][1].get("minimax_keyframes", []))
                for g in guide_frames:
                    g_img = g.get("frame")
                    g_idx = g.get("frame_idx", 0)
                    if g_img is not None or g.get("audio") is not None:
                        guide_cls = get_native_h3_node("MiniMaxH3AddGuide")
                        positive = native_outputs(guide_cls.execute(
                            positive=positive, latent=latent, frame_idx=g_idx,
                            vae=vae, audio_vae=audio_vae, image=g_img, audio=g.get("audio")))[0]

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
                    audio_latent = block.get("latent")
                    if audio_latent is None:
                        continue
                    decoded_items.append({"type": "audio"})
                    native_blocks.append({"kind": "audio", "ref_audio_t": int(audio_latent.shape[-1]), "audio_latent": audio_latent})
                    continue
                latent = block.get("latent")
                if latent is None:
                    continue

                # Check visual cache to avoid redundant VAE decoding across clips/runs
                name = block.get("name", "")
                mtime_ns = 0
                try:
                    mtime_ns = refmod_fingerprint(name)[0]
                except Exception:
                    pass
                from .cache_manager import fingerprint_value
                cache_name = f"{name}:{fingerprint_value(latent)}:{id(vae)}"
                cached_pixels = get_cached_visual_item(cache_name, mtime_ns) if name and mtime_ns else None

                if cached_pixels is not None:
                    pixels = cached_pixels
                else:
                    pixels = vae.decode(latent)
                    if getattr(pixels, "ndim", 0) == 5 and pixels.shape[0] == 1:
                        pixels = pixels[0]
                    if name and mtime_ns:
                        set_cached_visual_item(cache_name, mtime_ns, pixels)

                is_video = block.get("kind") == "video" or (getattr(latent, "ndim", 0) >= 5 and latent.shape[2] > 1)
                presentation = {"type": "image" if not is_video else "video", "data": pixels.cpu().clone()}
                if is_video:
                    indices = list(range(0, pixels.shape[0], int(FPS // 2)))
                    presentation["data"] = pixels[indices].cpu().clone()
                    presentation["timestamps"] = [i / FPS for i in indices]
                decoded_items.append(presentation)
                if is_video:
                    native_blocks.append({
                        "kind": block.get("kind", "video"),
                        "latent": latent,
                        "latent_t": int(latent.shape[2]),
                        "latent_h": int(latent.shape[-2]),
                        "latent_w": int(latent.shape[-1]),
                        "ref_audio_t": 0,
                        "audio_latent": None,
                    })
                else:
                    native_blocks.append({
                        "kind": "image",
                        "latent": latent,
                        "latent_h": int(latent.shape[-2]),
                        "latent_w": int(latent.shape[-1]),
                    })

            class RefClipWrapper:
                def tokenize(self, text, **kwargs):
                    kwargs["minimax_ref_items"] = list(kwargs.get("minimax_ref_items") or []) + decoded_items
                    return clip.tokenize(text, **kwargs)
                def encode_from_tokens_scheduled(self, tokens):
                    return clip.encode_from_tokens_scheduled(tokens)
            ref_clip = RefClipWrapper()

        positive, latent = native_outputs(node_cls.execute(
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
        ))

        if native_blocks:
            positive = [[emb, {**meta, "minimax_refs": list(meta.get("minimax_refs", [])) + native_blocks}] for emb, meta in positive]

        # Native guides can coexist with reference conditioning on current ComfyUI.
        anchors = list(guide_frames or [])
        if first_frame is not None:
            anchors.append({"frame": first_frame, "frame_idx": 0})
        if last_frame is not None:
            anchors.append({"frame": last_frame, "frame_idx": -1})
        for anchor in anchors:
            guide_cls = get_native_h3_node("MiniMaxH3AddGuide")
            positive = native_outputs(guide_cls.execute(
                positive=positive, latent=latent, frame_idx=anchor.get("frame_idx", 0),
                vae=vae, audio_vae=audio_vae, image=anchor.get("frame"),
                audio=anchor.get("audio")))[0]

        return positive, latent, prompt
