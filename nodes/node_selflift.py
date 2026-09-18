"""SelfLift configuration modifier node for MiniMax H3 Master Director."""

from __future__ import annotations

CATEGORY = "ComfyUI-AhmedAhmedEG"


class MiniMaxH3DirectorSelfLift:
    """Configures progressive first-pass sampling for the Master Director."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "lowres_scale": ("FLOAT", {"default": 0.5, "min": 0.25, "max": 1.0, "step": 0.05, "tooltip": "Spatial downscale ratio for initial noisy diffusion steps."}),
                "highres_steps": ("INT", {"default": 4, "min": 1, "max": 64, "step": 1, "tooltip": "Number of final steps to evaluate at full canvas resolution."}),
                "native_low_carry": ("BOOLEAN", {"default": True, "tooltip": "Carry over low-res context frames across multi-segment continuity."}),
            },
        }

    RETURN_TYPES = ("MMX_DIR_SELFLIFT",)
    RETURN_NAMES = ("selflift",)
    FUNCTION = "build_config"
    CATEGORY = CATEGORY

    def build_config(self, lowres_scale: float, highres_steps: int, native_low_carry: bool):
        return ({
            "enabled": True,
            "lowres_scale": float(lowres_scale),
            "highres_steps": int(highres_steps),
            "native_low_carry": bool(native_low_carry),
        },)
