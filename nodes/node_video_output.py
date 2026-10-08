"""Native ComfyUI VIDEO bridge for the consolidated Director's decoded output."""
from fractions import Fraction
import math


class MiniMaxH3VideoOutput:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"images": ("IMAGE",), "fps": ("FLOAT", {"default": 24., "min": .1, "max": 240.})},
                "optional": {"audio": ("AUDIO",)}}

    RETURN_TYPES = ("VIDEO",)
    RETURN_NAMES = ("video",)
    FUNCTION = "build"
    CATEGORY = "ComfyUI-AhmedAhmedEG"

    def build(self, images, fps=24., audio=None):
        if not math.isfinite(float(fps)) or fps <= 0 or images.shape[0] == 0:
            raise ValueError("VIDEO needs nonempty frames and a finite positive frame rate.")
        from comfy_api.latest import InputImpl, Types
        return (InputImpl.VideoFromComponents(Types.VideoComponents(
            images=images, audio=audio, frame_rate=Fraction(str(fps)))),)
