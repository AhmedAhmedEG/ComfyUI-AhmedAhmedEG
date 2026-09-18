"""Face Refinement configuration modifier node for MiniMax H3 Master Director."""

from __future__ import annotations

CATEGORY = "ComfyUI-AhmedAhmedEG"


class MiniMaxH3DirectorFaceRefine:
    """Configures facial tracking, close-up crop refinement, and seamless feather stitching."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "enabled": ("BOOLEAN", {"default": True, "tooltip": "Toggle face detail refinement"}),
                "prompt": ("STRING", {"default": "cinematic detailed portrait face, sharp focus, natural skin texture", "multiline": True}),
                "strength": ("FLOAT", {"default": 0.35, "min": 0.05, "max": 1.0, "step": 0.01}),
                "crop_size": ("INT", {"default": 512, "min": 256, "max": 1024, "step": 32}),
            },
        }

    RETURN_TYPES = ("MMX_DIR_FACE_REFINE",)
    RETURN_NAMES = ("face_refine",)
    FUNCTION = "build_config"
    CATEGORY = CATEGORY

    def build_config(self, prompt: str, strength: float, crop_size: int, enabled: bool = True):
        return ({
            "enabled": bool(enabled),
            "prompt": str(prompt).strip(),
            "strength": float(strength),
            "crop_size": int(crop_size),
        },)
