"""MiniMax H3 Director Settings and Configuration Nodes.

Provides dedicated, beautifully organized configuration nodes for sampling, canvas,
and pipeline settings, uncluttering the Master Director timeline node.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

log = logging.getLogger("MiniMaxH3MasterDirector.settings")

MMX_DIRECTOR_CONFIG = "MMX_DIRECTOR_CONFIG"
CATEGORY = "ComfyUI-AhmedAhmedEG"


class MiniMaxH3DirectorSettings:
    """Unified configuration node for MiniMax H3 Master Director.

    Consolidates canvas dimensions, sampling parameters, and pipeline options into
    a single reusable configuration pack.
    """

    @classmethod
    def INPUT_TYPES(cls):
        import comfy.samplers

        return {
            "required": {
                # Format & Canvas Settings
                "width": ("INT", {"default": 1344, "min": 32, "max": 4096, "step": 32, "tooltip": "Output video width in pixels."}),
                "height": ("INT", {"default": 768, "min": 32, "max": 4096, "step": 32, "tooltip": "Output video height in pixels."}),
                "frame_rate": ("FLOAT", {"default": 24.0, "min": 24.0, "max": 24.0, "step": 1.0, "tooltip": "H3 generates synchronized audio/video at 24 FPS."}),

                # Sampling Settings
                "steps": ("INT", {"default": 25, "min": 1, "max": 200, "step": 1, "tooltip": "Sampling steps for DiT diffusion."}),
                "cfg": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 20.0, "step": 0.1, "tooltip": "Classifier-free guidance scale (1.0 for standard Turbo/H3)."}),
                "sampler": (comfy.samplers.KSampler.SAMPLERS, {"default": "res_multistep", "tooltip": "Diffusion ODE/SDE sampler."}),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS, {"default": "simple", "tooltip": "Noise schedule type."}),
                "shift_video": ("FLOAT", {"default": 12.0, "min": 0.1, "max": 100.0, "step": 0.1, "tooltip": "Sigma shift exponent for video stream."}),
                "shift_audio": ("FLOAT", {"default": 3.0, "min": 0.1, "max": 100.0, "step": 0.1, "tooltip": "Sigma shift exponent for audio stream."}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF, "tooltip": "Base random seed."}),

            },
            "optional": {
                "settings_optional": (MMX_DIRECTOR_CONFIG, {"tooltip": "Optional previous configuration to chain or override."}),
                "canvas_policy": (["manual", "original", "auto"], {"default": "manual", "tooltip": "Manual uses width/height; Original follows source dimensions; Auto uses megapixels/aspect."}),
                "canvas_megapixels": ("FLOAT", {"default": 1.0, "min": 0.01, "max": 16.0, "step": 0.1, "tooltip": "Used only by Auto canvas."}),
                "canvas_aspect": (["16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "3:2", "2:3", "auto"], {"default": "16:9", "tooltip": "Used only by Auto canvas; auto follows source aspect."}),
            },
        }

    RETURN_TYPES = (MMX_DIRECTOR_CONFIG,)
    RETURN_NAMES = ("config",)
    FUNCTION = "build_config"
    CATEGORY = CATEGORY
    DESCRIPTION = "Configures all canvas, sampling, and pipeline settings for MiniMax H3 Master Director."

    def build_config(
        self,
        width: int = 1344,
        height: int = 768,
        frame_rate: float = 24.0,
        steps: int = 25,
        cfg: float = 1.0,
        sampler: str = "res_multistep",
        scheduler: str = "simple",
        shift_video: float = 12.0,
        shift_audio: float = 3.0,
        seed: int = 0,
        generation_mode: str = None,
        execution_mode: str = "All-in-One Generation",
        prompt_mode: str = "structured",
        run_mode: str = "clip_by_clip",
        continuity_mode: str = "Motion Context (Chained)",
        context_length: str = "22",
        preview_mode: str = "full",
        settings_optional: Optional[Dict[str, Any]] = None,
        canvas_policy: str = "manual",
        canvas_megapixels: float = 1.0,
        canvas_aspect: str = "16:9",
        **kwargs,
    ) -> Tuple[Dict[str, Any]]:
        if generation_mode is not None:
            if generation_mode not in ("Next shot", "All shots", "Conditioning only"):
                raise ValueError("Unknown generation mode.")
            execution_mode = "Conditioning Guide Output" if generation_mode == "Conditioning only" else "All-in-One Generation"
            run_mode = "full_batch" if generation_mode == "All shots" else "clip_by_clip"
            prompt_mode = "simple"
        cfg_dict = {
            "resolution": {"mode": canvas_policy, "width": int(width), "height": int(height),
                           "megapixels": float(canvas_megapixels), "aspect": canvas_aspect},
            "width": int(width),
            "height": int(height),
            "frame_rate": float(frame_rate),
            "steps": int(steps),
            "cfg": float(cfg),
            "sampler": str(sampler),
            "scheduler": str(scheduler),
            "shift_video": float(shift_video),
            "shift_audio": float(shift_audio),
            "seed": int(seed),
            "execution_mode": str(execution_mode),
            "prompt_mode": str(prompt_mode),
            "run_mode": str(run_mode),
            "continuity_mode": str(continuity_mode),
            "context_length": str(context_length),
            "preview_mode": str(preview_mode),
        }

        # Merge with optional chained settings (incoming settings take precedence unless overridden)
        if settings_optional is not None and isinstance(settings_optional, dict):
            merged = dict(settings_optional)
            merged.update(cfg_dict)
            cfg_dict = merged

        return (cfg_dict,)
