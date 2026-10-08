"""Refine & Upscale configuration modifier node for MiniMax H3 Master Director."""

from __future__ import annotations

CATEGORY = "ComfyUI-AhmedAhmedEG"


class MiniMaxH3DirectorRefine:
    """Configures second-pass refinement, spatial tiled sampling, and latent upscaling."""

    @classmethod
    def INPUT_TYPES(cls):
        import comfy.samplers
        try:
            from ..core.vendor.aimixer.director.h3_latent_upscale import list_h3_latent_upscale_models
        except ImportError:
            from core.vendor.aimixer.director.h3_latent_upscale import list_h3_latent_upscale_models
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
                "passes": ("INT", {"default": 1, "min": 1, "max": 20}),
                "sampler": (comfy.samplers.KSampler.SAMPLERS,),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS,),
                "latent_upscale_model": (["interpolate", *list_h3_latent_upscale_models()],),
                "enable_latent_chunking": ("BOOLEAN", {"default": False}),
                "backend": (["global", "sampler"], {"default": "global"}),
                "memory_budget_mb": ("INT", {"default": 0, "min": 0, "max": 131072}),
                "upscale_precision": (["auto", "bf16", "fp16", "fp32"],),
            },
            "optional": {
                "refine_model": ("MODEL", {"tooltip": "Optional alternative UNET model for the second pass (e.g. non-turbo model)."}),
                "sigmas": ("SIGMAS",),
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
        passes=1, sampler="euler", scheduler="simple", latent_upscale_model="interpolate",
        enable_latent_chunking=False, sigmas=None,
        backend="global", memory_budget_mb=0, upscale_precision="auto",
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
            "passes": int(passes), "sampler": sampler, "scheduler": scheduler,
            "latent_upscale_model": None if latent_upscale_model == "interpolate" else latent_upscale_model,
            "enable_latent_chunking": bool(enable_latent_chunking), "sigmas": sigmas,
            "backend": backend, "memory_budget_mb": int(memory_budget_mb),
            "upscale_precision": upscale_precision,
        },)
