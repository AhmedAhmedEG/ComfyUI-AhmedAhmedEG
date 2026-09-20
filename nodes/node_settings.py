"""MiniMax H3 Director Settings and Configuration Nodes.

Provides dedicated, beautifully organized configuration nodes for sampling, canvas,
and pipeline settings, uncluttering the Master Director timeline node.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

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
                "frame_rate": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 120.0, "step": 0.1, "tooltip": "Output video frame rate (FPS)."}),

                # Sampling Settings
                "steps": ("INT", {"default": 25, "min": 1, "max": 200, "step": 1, "tooltip": "Sampling steps for DiT diffusion."}),
                "cfg": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 20.0, "step": 0.1, "tooltip": "Classifier-free guidance scale (1.0 for standard Turbo/H3)."}),
                "sampler": (comfy.samplers.KSampler.SAMPLERS, {"default": "res_multistep", "tooltip": "Diffusion ODE/SDE sampler."}),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS, {"default": "simple", "tooltip": "Noise schedule type."}),
                "shift_video": ("FLOAT", {"default": 12.0, "min": 0.1, "max": 100.0, "step": 0.1, "tooltip": "Sigma shift exponent for video stream."}),
                "shift_audio": ("FLOAT", {"default": 3.0, "min": 0.1, "max": 100.0, "step": 0.1, "tooltip": "Sigma shift exponent for audio stream."}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF, "tooltip": "Base random seed."}),

                # Pipeline & Continuity Settings
                "execution_mode": (["All-in-One Generation", "Conditioning Guide Output"], {"default": "All-in-One Generation", "tooltip": "Choose between full in-node generation or emitting positive/latent for custom graphs."}),
                "prompt_mode": (["structured", "simple"], {"default": "structured", "tooltip": "Structured prompts assemble IMD, soundscape, and music sections."}),
                "run_mode": (["clip_by_clip", "full_batch"], {"default": "clip_by_clip", "tooltip": "Generate sequential shots individually or in one batch."}),
                "continuity_mode": (["Motion Context (Chained)", "Independent (No Continuity)", "FL2VA Tail Handoff"], {"default": "Motion Context (Chained)", "tooltip": "How adjacent shots link motion and style continuity."}),
                "context_length": (["22", "5", "39", "56"], {"default": "22", "tooltip": "Number of latent frames passed across shot seams."}),
                "preview_mode": (["full", "unvalidated_only"], {"default": "full", "tooltip": "Preview output: 'full' for complete sequence, 'unvalidated_only' for new/unvalidated clips only."}),
            },
            "optional": {
                "settings_optional": (MMX_DIRECTOR_CONFIG, {"tooltip": "Optional previous configuration to chain or override."}),
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
        execution_mode: str = "All-in-One Generation",
        prompt_mode: str = "structured",
        run_mode: str = "clip_by_clip",
        continuity_mode: str = "Motion Context (Chained)",
        context_length: str = "22",
        preview_mode: str = "full",
        settings_optional: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Tuple[Dict[str, Any]]:
        cfg_dict = {
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


class MiniMaxH3SamplingSettings:
    """Specialized modular node for DiT sampling parameters."""

    @classmethod
    def INPUT_TYPES(cls):
        import comfy.samplers

        return {
            "required": {
                "steps": ("INT", {"default": 25, "min": 1, "max": 200, "step": 1}),
                "cfg": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 20.0, "step": 0.1}),
                "sampler": (comfy.samplers.KSampler.SAMPLERS, {"default": "res_multistep"}),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS, {"default": "simple"}),
                "shift_video": ("FLOAT", {"default": 12.0, "min": 0.1, "max": 100.0, "step": 0.1}),
                "shift_audio": ("FLOAT", {"default": 3.0, "min": 0.1, "max": 100.0, "step": 0.1}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
            },
            "optional": {
                "settings_optional": (MMX_DIRECTOR_CONFIG, {"tooltip": "Optional previous configuration to chain or override."}),
            },
        }

    RETURN_TYPES = (MMX_DIRECTOR_CONFIG,)
    RETURN_NAMES = ("config",)
    FUNCTION = "build_sampling_config"
    CATEGORY = CATEGORY
    DESCRIPTION = "Configures DiT diffusion sampling parameters (steps, cfg, sampler, scheduler, shifts, seed)."

    def build_sampling_config(
        self,
        steps: int = 25,
        cfg: float = 1.0,
        sampler: str = "res_multistep",
        scheduler: str = "simple",
        shift_video: float = 12.0,
        shift_audio: float = 3.0,
        seed: int = 0,
        settings_optional: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Tuple[Dict[str, Any]]:
        base = dict(settings_optional) if settings_optional and isinstance(settings_optional, dict) else {}
        base.update({
            "steps": int(steps),
            "cfg": float(cfg),
            "sampler": str(sampler),
            "scheduler": str(scheduler),
            "shift_video": float(shift_video),
            "shift_audio": float(shift_audio),
            "seed": int(seed),
        })
        return (base,)
