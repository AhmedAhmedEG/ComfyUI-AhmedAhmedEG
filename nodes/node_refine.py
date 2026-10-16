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
                "passes": ("INT", {"default": 1, "min": 1, "max": 9999}),
                "sampler": (comfy.samplers.KSampler.SAMPLERS,),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS,),
                "latent_upscale_model": (["interpolate", "Auto Download H3 Upscaler", *list_h3_latent_upscale_models()],),
                "enable_latent_chunking": ("BOOLEAN", {"default": False}),
                "backend": (["global", "sampler"], {"default": "global", "tooltip": "Global refines video while retaining first-pass audio. Sampler refines the joint audiovisual latent, so its audio can change too."}),
                "memory_budget_mb": ("INT", {"default": 0, "min": 0, "max": 131072}),
                "upscale_precision": (["auto", "bf16", "fp16", "fp32"],),
                "confirm_first_pass": ("BOOLEAN", {"default":False, "tooltip":"Pause after the initial pass; approve it on its timeline card, then run refinement without repeating initial sampling."}),
                "skip_fl2v": ("BOOLEAN", {"default":True, "tooltip":"Skip refinement for first-and-last-frame clips to protect their endpoints."}),
                "upscale_method": (["latent","learned_pixel","RTX VSR","bicubic","lanczos"],),
                "spike_guard": ("BOOLEAN", {"default":False,"tooltip":"Experimental learned latent burn-signature correction. Off by default."}),
                "guard_sensitivity": ("FLOAT", {"default":4.3,"min":1.,"max":20.}),
                "guard_strength": ("FLOAT", {"default":1.,"min":0.,"max":1.}),
            },
            "optional": {
                "refine_model": ("MODEL", {"tooltip": "Optional alternative UNET model for the second pass (e.g. non-turbo model)."}),
                "sigmas": ("SIGMAS",),
                "upscale_model": ("UPSCALE_MODEL",),
                "seed_policy": (["legacy","inherit","offset","independent"], {"default":"legacy","tooltip":"Legacy increments the clip seed per pass. Inherit keeps it fixed; Offset starts at clip seed + 1; Independent uses the refine seed."}),
                "refine_seed": ("STRING", {"default":"0","tooltip":"Unsigned 64-bit decimal seed; only used by Independent."}),
                "canvas_policy": (["manual","follow"], {"default":"manual","tooltip":"Follow preserves the actual first-pass aspect and uses Megapixels. Manual uses target dimensions."}),
                "megapixels": ("FLOAT", {"default":1.8,"min":.01,"max":16.,"step":.1,"tooltip":"Target pixel budget when following the actual first-pass aspect. Dimensions snap to H3's 32-pixel grid."}),
                "resize_method": (["Stretch","Center Crop (Fill)","Letterbox (Fit)"], {"default":"Stretch","tooltip":"Pixel preparation aspect policy. Stretch preserves old workflow behavior."}),
                "memory_planning": ("BOOLEAN", {"default":True,"tooltip":"Enforce the conservative global refinement memory estimate."}),
                "memory_reserve_pct": ("FLOAT", {"default":35.,"min":0.,"max":100.,"step":1.,"tooltip":"Workspace headroom after managed weights and device reservations. A heuristic, not a guaranteed peak VRAM limit."}),
                "guard_mode": (["burn_direction","both"], {"default":"burn_direction","tooltip":"Correct the learned burn direction only, or positive and negative outliers."}),
                "seed_after_generate": (["fixed","increment","decrement","randomize"], {"default":"fixed","tooltip":"Advance the independent refine seed after a successful refinement run. Leaves the clip's first-pass seed untouched."}),
            },
            "hidden":{"unique_id":"UNIQUE_ID"},
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
        backend="global", memory_budget_mb=0, upscale_precision="auto", confirm_first_pass=False, skip_fl2v=True,
        upscale_method="latent", upscale_model=None, spike_guard=False, guard_sensitivity=4.3, guard_strength=1.,
        seed_policy="legacy", refine_seed="0", canvas_policy="manual", megapixels=1.8, resize_method="Stretch",
        seed_after_generate="fixed", unique_id=None, memory_planning=True, memory_reserve_pct=35., guard_mode="burn_direction",
    ):
        try:
            from ..core.refine_controls import refine_seed as validate_seed, MAX_REFINE_PASSES
        except ImportError:
            from core.refine_controls import refine_seed as validate_seed, MAX_REFINE_PASSES
        validate_seed(0,seed_policy,refine_seed)
        import math
        if seed_after_generate not in ("fixed","increment","decrement","randomize"):raise ValueError("Unknown refine seed advancement.")
        if guard_mode not in ("burn_direction","both"):raise ValueError("Unknown Spike Guard mode.")
        if not math.isfinite(float(memory_reserve_pct)) or not 0<=float(memory_reserve_pct)<=100:raise ValueError("Invalid memory reserve percentage.")
        if not 1<=int(passes)<=MAX_REFINE_PASSES: raise ValueError('Invalid refinement pass count.')
        if enabled and latent_upscale_model=='Auto Download H3 Upscaler':
            if upscale_method!='latent':raise ValueError('Automatic H3 upscaler requires latent preparation.')
            try:
                from ..core.model_downloads import ensure_h3_upscaler
            except ImportError:
                from core.model_downloads import ensure_h3_upscaler
            latent_upscale_model=ensure_h3_upscaler()
        return ({
            "memory_planning":bool(memory_planning),"memory_reserve_pct":float(memory_reserve_pct),"guard_mode":guard_mode,
            "seed_policy":seed_policy,"refine_seed":str(refine_seed),"canvas_policy":canvas_policy,
            "seed_after_generate":seed_after_generate,"owner_id":str(unique_id) if unique_id is not None else None,
            "megapixels":float(megapixels),"resize_method":resize_method,
            "enabled": bool(enabled), "confirm_first_pass":bool(confirm_first_pass), "skip_fl2v":bool(skip_fl2v),
            "upscale_method":upscale_method,"upscale_model":upscale_model, "spike_guard":bool(spike_guard),
            "guard_sensitivity":float(guard_sensitivity),"guard_strength":float(guard_strength),
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
