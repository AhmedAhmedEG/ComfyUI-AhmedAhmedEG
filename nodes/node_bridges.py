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

    RETURN_TYPES = ("MMX_REF_PACK",)
    RETURN_NAMES = ("ref_pack",)
    FUNCTION = "build_pack"
    CATEGORY = CATEGORY

    def build_pack(self, **kwargs):
        refs = []
        pack = {"version": 1}
        for i in range(1, 10):
            img = kwargs.get(f"ref_{i}")
            if img is None:
                img = kwargs.get(f"image_{i}")
            if img is not None:
                pack[f"ref_image_{i}"] = img
                refs.append({
                    "id": f"ref_img_{i}",
                    "name": f"Picture {i}",
                    "type": "image",
                    "data": img,
                })
        pack["refs"] = refs
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
