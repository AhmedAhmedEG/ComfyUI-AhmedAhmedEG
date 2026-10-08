"""SelfLift configuration modifier node for MiniMax H3 Master Director."""

from __future__ import annotations

CATEGORY = "ComfyUI-AhmedAhmedEG"


class MiniMaxH3DirectorSelfLift:
    """Configures progressive first-pass sampling for the Master Director."""

    @classmethod
    def INPUT_TYPES(cls):
        try:
            from ..core.vendor.aimixer.director.h3_latent_upscale import list_h3_latent_upscale_models
        except ImportError:
            from core.vendor.aimixer.director.h3_latent_upscale import list_h3_latent_upscale_models
        return {
            "required": {
                "lowres_scale": ("FLOAT", {"default": 0.5, "min": 0.25, "max": 1.0, "step": 0.05, "tooltip": "Spatial downscale ratio for initial noisy diffusion steps."}),
                "highres_steps": ("INT", {"default": 4, "min": 1, "max": 64, "step": 1, "tooltip": "Number of final steps to evaluate at full canvas resolution."}),
                "native_low_carry": ("BOOLEAN", {"default": True, "tooltip": "Carry over low-res context frames across multi-segment continuity."}),
                "split_mode": (["highres_steps", "transition_step"],),
                "transition_step": ("INT", {"default": 6, "min": 1, "max": 200}),
                "latent_upscale_model": (list_h3_latent_upscale_models(),),
                "sampler_mode": (["euler", "follow_director"],),
                "rho": ("FLOAT", {"default": 0., "min": 0., "max": 1.}),
                "w_min": ("FLOAT", {"default": .5, "min": 0., "max": 1.}),
                "w_max": ("FLOAT", {"default": 1., "min": 0., "max": 1.}),
                "latent_upsample": (["bilinear", "nearest"],),
                "enable_latent_chunking": ("BOOLEAN", {"default": False}),
                "enable_tiling": ("BOOLEAN", {"default": False}),
                "tile_count": ("INT", {"default": 2, "min": 1, "max": 8}),
                "tile_overlap": ("INT", {"default": 128, "min": 0, "max": 2048, "step": 32}),
            },
            "optional": {"model_hires": ("MODEL",)},
        }

    RETURN_TYPES = ("MMX_DIR_SELFLIFT",)
    RETURN_NAMES = ("selflift",)
    FUNCTION = "build_config"
    CATEGORY = CATEGORY

    def build_config(self, lowres_scale=.5, highres_steps=4, native_low_carry=True, **kwargs):
        try:
            from ..core.vendor.aimixer.director.selflift.pack import pack_selflift
        except ImportError:
            from core.vendor.aimixer.director.selflift.pack import pack_selflift
        return (pack_selflift(lowres_scale=lowres_scale, highres_steps=highres_steps,
            native_low_carry=native_low_carry, **kwargs),)
