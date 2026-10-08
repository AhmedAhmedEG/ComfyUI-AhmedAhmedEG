"""Face Refinement configuration modifier node for MiniMax H3 Master Director."""

from __future__ import annotations

CATEGORY = "ComfyUI-AhmedAhmedEG"


class MiniMaxH3DirectorFaceRefine:
    """Configures facial tracking, close-up crop refinement, and seamless feather stitching."""

    @classmethod
    def INPUT_TYPES(cls):
        import comfy.samplers
        return {
            "required": {
                "enabled": ("BOOLEAN", {"default": True, "tooltip": "Toggle face detail refinement"}),
                "prompt": ("STRING", {"default": "cinematic detailed portrait face, sharp focus, natural skin texture", "multiline": True}),
                "strength": ("FLOAT", {"default": 0.35, "min": 0.05, "max": 1.0, "step": 0.01}),
                "crop_size": ("INT", {"default": 512, "min": 256, "max": 1024, "step": 32}),
                "detector": ("STRING", {"default": "face_yolov8m.pt", "tooltip": "YOLO face detector weight in models/ultralytics/bbox/"}),
                "confidence": ("FLOAT", {"default": .35, "min": .05, "max": .95}),
                "crop_factor": ("FLOAT", {"default": 2.5, "min": 1.2, "max": 8.}),
                "canvas_mode": (["manual", "auto_capped_768"],),
                "select": (["largest_face", "centre_most"],),
                "paste_region": (["face_only", "face_ellipse", "full_crop"],),
                "mask_dilation": ("INT", {"default": 16, "min": 0, "max": 256}),
                "feather": ("INT", {"default": 24, "min": 0, "max": 256}),
                "colour_match": ("FLOAT", {"default": 1., "min": 0., "max": 1.}),
                "blend": ("FLOAT", {"default": 1., "min": 0., "max": 1.}),
                "steps": ("INT", {"default": 8, "min": 1, "max": 50}),
                "sampler": (comfy.samplers.KSampler.SAMPLERS,),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS,),
                "seed_mode": (["inherit", "offset"],),
            },
            "optional": {"sigmas": ("SIGMAS",)},
        }

    RETURN_TYPES = ("MMX_DIR_FACE_REFINE",)
    RETURN_NAMES = ("face_refine",)
    FUNCTION = "build_config"
    CATEGORY = CATEGORY

    def build_config(self, prompt: str, strength: float, crop_size: int, detector: str = "face_yolov8m.pt", enabled: bool = True, **kwargs):
        return ({
            "enabled": bool(enabled),
            "prompt": str(prompt).strip(),
            "strength": float(strength),
            "crop_size": int(crop_size),
            "detector": str(detector).strip(),
            **kwargs,
        },)
