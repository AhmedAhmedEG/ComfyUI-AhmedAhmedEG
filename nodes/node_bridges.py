"""Reference Pack and Prompt Pack Bridge nodes for MiniMax H3 Master Director."""

from __future__ import annotations

from typing import Any, Dict, Optional
import torch

CATEGORY = "ComfyUI-AhmedAhmedEG"


class MiniMaxH3ReferenceBridge:
    """Bridges external ComfyUI IMAGE outputs into the Master Director's reference slots."""

    @classmethod
    def INPUT_TYPES(cls):
        optional = {}
        for i in range(1, 10):
            optional[f"ref_{i}"] = ("IMAGE", {"tooltip": f"External IMAGE for <Picture {i}>"})
            optional[f"image_{i}"] = ("IMAGE", {"tooltip": f"Alias for <Picture {i}>"})
        return {"required": {}, "optional": optional}

    RETURN_TYPES = ("REF_PACK",)
    RETURN_NAMES = ("ref_pack",)
    FUNCTION = "build_pack"
    CATEGORY = CATEGORY

    def build_pack(self, **kwargs):
        pack = {}
        for i in range(1, 10):
            img = kwargs.get(f"ref_{i}") or kwargs.get(f"image_{i}")
            if img is not None:
                pack[f"ref_image_{i}"] = img
        return (pack,)


class MiniMaxH3PromptBridge:
    """Bridges external multi-line text or prompt generators into clip prompt slots."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompts_text": ("STRING", {"default": "", "multiline": True, "tooltip": "Newline-separated list of clip prompts"}),
            },
        }

    RETURN_TYPES = ("PROMPT_PACK",)
    RETURN_NAMES = ("prompt_pack",)
    FUNCTION = "build_pack"
    CATEGORY = CATEGORY

    def build_pack(self, prompts_text: str):
        lines = [line.strip() for line in str(prompts_text or "").split("\n") if line.strip()]
        return ({"prompts": lines},)
