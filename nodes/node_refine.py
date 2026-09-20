"""Refine & Upscale configuration modifier node for MiniMax H3 Master Director."""

from __future__ import annotations

CATEGORY = "ComfyUI-AhmedAhmedEG"


class MiniMaxH3DirectorRefine:
    """Configures second-pass refinement, spatial tiled sampling, and latent upscaling."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "enabled": ("BOOLEAN", {"default": True, "tooltip": "Toggle 2nd-pass refinement"}),
                "mode": (["refine", "upscale", "latent_upscale"], {"default": "refine", "tooltip": "Refinement mode"}),
                "steps": ("INT", {"default": 3, "min": 1, "max": 50, "step": 1, "tooltip": "Refine sampling steps"}),
                "denoise": ("FLOAT", {"default": 0.45, "min": 0.05, "max": 1.0, "step": 0.01, "tooltip": "Denoise strength for refine sample"}),
                "target_width": ("INT", {"default": 1792, "min": 32, "max": 4096, "step": 32, "tooltip": "Target upscale width"}),
                "target_height": ("INT", {"default": 1024, "min": 32, "max": 4096, "step": 32, "tooltip": "Target upscale height"}),
                "enable_tiling": ("BOOLEAN", {"default": False, "tooltip": "Enable spatial tiled sampling to conserve VRAM on high resolutions"}),
                "tile_count": ("INT", {"default": 2, "min": 1, "max": 8, "step": 1}),
                "tile_overlap": ("INT", {"default": 128, "min": 16, "max": 512, "step": 16, "tooltip": "Tile overlap in pixels"}),
            },
            "optional": {
                "refine_model": ("MODEL", {"tooltip": "Optional alternative UNET model for the second pass (e.g. non-turbo model)."}),
            },
        }

    RETURN_TYPES = ("MMX_DIR_REFINE",)
    RETURN_NAMES = ("refine",)
    FUNCTION = "build_config"
    CATEGORY = CATEGORY

    def build_config(
        self,
        mode: str,
        steps: int,
        denoise: float,
        target_width: int,
        target_height: int,
        enable_tiling: bool,
        tile_count: int,
        tile_overlap: int = 128,
        enabled: bool = True,
        refine_model=None,
    ):
        return ({
            "enabled": bool(enabled),
            "mode": mode,
            "steps": int(steps),
            "denoise": float(denoise),
            "target_width": int(target_width),
            "target_height": int(target_height),
            "enable_tiling": bool(enable_tiling),
            "tile_count": int(tile_count),
            "tile_overlap": int(tile_overlap),
            "refine_model": refine_model,
        },)
