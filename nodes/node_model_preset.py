"""Three-way REF2VA model preset: Base, Lightning LoRA or Fast H3.

Selects one prepared model branch (and its video VAE) and the sampling values
that branch requires. Inputs are lazy, so only the chosen branch is loaded.
Director Settings applies the returned sampling values over its own widgets.
"""

from __future__ import annotations

try:
    from ..core.model_preset import PRESETS, selected_inputs, preset_sampling
except ImportError:
    from core.model_preset import PRESETS, selected_inputs, preset_sampling

MMX_SAMPLING_PRESET = "MMX_SAMPLING_PRESET"


class MiniMaxH3ModelPreset:
    @classmethod
    def INPUT_TYPES(cls):
        lazy = {"lazy": True}
        return {
            "required": {
                "preset": (list(PRESETS), {"default": "Base", "tooltip": "Which REF2VA model branch to use. Fast H3 always samples with its required settings: 8 steps, euler, simple, CFG 1, shift 12/3."}),
                "base_steps": ("INT", {"default": 20, "min": 1, "max": 200, "tooltip": "Sampling steps for the Base preset. Sampler, scheduler and CFG come from Director Settings."}),
                "lightning_steps": ("INT", {"default": 8, "min": 1, "max": 200, "tooltip": "Sampling steps for the Lightning LoRA preset. Sampler, scheduler and CFG come from Director Settings."}),
            },
            "optional": {
                "base_model": ("MODEL", {**lazy, "tooltip": "Base REF2VA model branch (with its attention node)."}),
                "lightning_model": ("MODEL", {**lazy, "tooltip": "REF2VA model with the Lightning/turbo LoRA applied (with its attention node)."}),
                "fast_model": ("MODEL", {**lazy, "tooltip": "Fast H3 branch: UNET → Model Attention Backend → Block Sparse Attention (vsa), as in the Fast H3 workflow."}),
                "video_vae": ("VAE", {**lazy, "tooltip": "Video VAE for Base and Lightning (and Fast H3 if fast_video_vae is not connected)."}),
                "fast_video_vae": ("VAE", {**lazy, "tooltip": "Video VAE used with Fast H3 (the Fast H3 workflow uses the int8 convrot video VAE)."}),
            },
        }

    RETURN_TYPES = ("MODEL", "VAE", MMX_SAMPLING_PRESET)
    RETURN_NAMES = ("model", "video_vae", "sampling")
    FUNCTION = "select"
    CATEGORY = "ComfyUI-AhmedAhmedEG"
    DESCRIPTION = "Switch the REF2VA model between Base, Lightning LoRA and Fast H3, with the matching video VAE and sampling values."

    def check_lazy_status(self, preset, base_steps=20, lightning_steps=8, **inputs):
        names = selected_inputs(preset, inputs.keys())
        return [name for name in names if name in inputs and inputs[name] is None]

    def select(self, preset, base_steps=20, lightning_steps=8, **inputs):
        model_name, vae_name = selected_inputs(preset, inputs.keys())
        model, vae = inputs.get(model_name), inputs.get(vae_name)
        if model is None:
            raise ValueError(f"Model preset {preset!r} needs its {model_name} input connected.")
        if vae is None:
            raise ValueError(f"Model preset {preset!r} needs {vae_name} connected.")
        return (model, vae, preset_sampling(preset, base_steps, lightning_steps))
