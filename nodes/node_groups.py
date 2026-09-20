"""External graph packer nodes for MiniMax H3 Director: Image to Video & Reference to Video groups."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import torch

MMX_DIR_GROUP = "MMX_DIR_GROUP"
CATEGORY = "ComfyUI-AhmedAhmedEG"
DEFAULT_DURATION = 5.0


def _normalize_group(g: Any) -> List[Dict[str, Any]]:
    if g is None:
        return []
    if isinstance(g, dict):
        return [g]
    if isinstance(g, (list, tuple)):
        out = []
        for item in g:
            out.extend(_normalize_group(item))
        return out
    return []


class MiniMaxH3DirectorGroupImageToVideo:
    """Packs one Image-to-Video group (t2v / i2v / fl2v) for the Director."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True, "default": "", "tooltip": "Prompt for this clip group."}),
                "duration_sec": ("FLOAT", {"default": DEFAULT_DURATION, "min": 0.2, "max": 120.0, "step": 0.1, "tooltip": "Duration in seconds."}),
            },
            "optional": {
                "first_frame": ("IMAGE", {"tooltip": "Optional first frame for i2v / fl2v."}),
                "last_frame": ("IMAGE", {"tooltip": "Optional last frame for fl2v / l2v."}),
            },
        }

    RETURN_TYPES = (MMX_DIR_GROUP,)
    RETURN_NAMES = ("group",)
    FUNCTION = "pack"
    CATEGORY = CATEGORY
    DESCRIPTION = "Pack one MiniMax H3 Image to Video group (t2v / i2v / fl2v)."

    def pack(self, prompt="", duration_sec=DEFAULT_DURATION, first_frame=None, last_frame=None, **kwargs):
        kind = "fl2v" if (first_frame is not None and last_frame is not None) else (
            "i2v" if first_frame is not None else ("l2v" if last_frame is not None else "t2v")
        )
        group = {
            "family": "i2v",
            "kind": kind,
            "prompt": str(prompt or ""),
            "duration_sec": float(duration_sec),
            "first_frame": first_frame,
            "last_frame": last_frame,
        }
        return (group,)


class MiniMaxH3DirectorGroupReferenceToVideo:
    """Packs one Reference-to-Video group for the Director."""

    @classmethod
    def INPUT_TYPES(cls):
        optional = {
            "ref_images": ("REF_PACK", {"tooltip": "Optional reference images pack."}),
        }
        for i in range(1, 10):
            optional[f"ref_image_{i}"] = ("IMAGE", {"tooltip": f"Reference picture {i}"})
        optional["ref_video_1"] = ("IMAGE", {"tooltip": "Reference video 1 frames"})
        optional["ref_audio_1"] = ("AUDIO", {"tooltip": "Reference audio 1"})

        return {
            "required": {
                "prompt": ("STRING", {"multiline": True, "default": "", "tooltip": "Prompt for this clip group."}),
                "duration_sec": ("FLOAT", {"default": DEFAULT_DURATION, "min": 0.2, "max": 120.0, "step": 0.1, "tooltip": "Duration in seconds."}),
                "ref_image_size": (["match", "1024", "1280", "1536", "max"], {"default": "match"}),
            },
            "optional": optional,
        }

    RETURN_TYPES = (MMX_DIR_GROUP,)
    RETURN_NAMES = ("group",)
    FUNCTION = "pack"
    CATEGORY = CATEGORY
    DESCRIPTION = "Pack one MiniMax H3 Reference to Video group (REF2VA)."

    def pack(self, prompt="", duration_sec=DEFAULT_DURATION, ref_image_size="match", ref_images=None, **kwargs):
        images = {}
        if isinstance(ref_images, dict):
            for k, v in ref_images.items():
                if v is not None:
                    images[k] = v

        for i in range(1, 10):
            val = kwargs.get(f"ref_image_{i}")
            if val is not None:
                images[f"ref_image_{i}"] = val

        videos = {}
        if kwargs.get("ref_video_1") is not None:
            videos["ref_video_1"] = kwargs.get("ref_video_1")

        audios = {}
        if kwargs.get("ref_audio_1") is not None:
            audios["ref_audio_1"] = kwargs.get("ref_audio_1")

        group = {
            "family": "r2v",
            "kind": "r2v",
            "prompt": str(prompt or ""),
            "duration_sec": float(duration_sec),
            "ref_image_size": ref_image_size,
            "ref_images": images,
            "ref_videos": videos,
            "ref_audios": audios,
        }
        return (group,)


class MiniMaxH3DirectorGroupsCombine:
    """Combines multiple Director groups into an ordered list for batch execution."""

    @classmethod
    def INPUT_TYPES(cls):
        optional = {}
        for i in range(1, 11):
            optional[f"group_{i}"] = (MMX_DIR_GROUP, {"tooltip": f"Group slot {i}"})
        return {"required": {}, "optional": optional}

    RETURN_TYPES = (MMX_DIR_GROUP,)
    RETURN_NAMES = ("groups",)
    FUNCTION = "combine"
    CATEGORY = CATEGORY
    DESCRIPTION = "Combine multiple Image-to-Video or Reference-to-Video groups into one ordered batch."

    def combine(self, **kwargs):
        combined = []
        for i in range(1, 11):
            g = kwargs.get(f"group_{i}")
            if g is not None:
                combined.extend(_normalize_group(g))

        if not combined:
            raise ValueError("Director Groups Combine: connect at least one group.")

        return (combined,)
