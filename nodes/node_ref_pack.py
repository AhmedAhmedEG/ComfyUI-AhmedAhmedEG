"""MiniMax H3 Reference Pack (RefPool) Node.

Provides an unlimited pool of image, video, and audio references for timeline clips.
Clips on the timeline locally select which references they use, preventing global contamination.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import torch

log = logging.getLogger("MiniMaxH3MasterDirector.ref_pack")

MMX_REF_PACK = "MMX_REF_PACK"
CATEGORY = "ComfyUI-AhmedAhmedEG"


class MiniMaxH3RefPack:
    """Pools image, video, and audio references with labels for local assignment in timeline clips."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "ref_pack_optional": (MMX_REF_PACK, {"tooltip": "Optional previous RefPack to daisy-chain for unlimited references."}),
                
                # Image references
                "image_1": ("IMAGE", {"tooltip": "Reference image 1 (e.g. character, style, face, start frame)."}),
                "image_2": ("IMAGE", {"tooltip": "Reference image 2."}),
                "image_3": ("IMAGE", {"tooltip": "Reference image 3."}),
                "image_4": ("IMAGE", {"tooltip": "Reference image 4."}),

                # Video references
                "video_1": ("IMAGE", {"tooltip": "Reference video 1 (frame batch) for V2V / RV2V."}),
                "video_2": ("IMAGE", {"tooltip": "Reference video 2 (frame batch)."}),

                # Audio references
                "audio_1": ("AUDIO", {"tooltip": "Reference audio 1 (e.g. speech, music, soundscape)."}),
                "audio_2": ("AUDIO", {"tooltip": "Reference audio 2."}),

                # RefMod references (.safetensors character/concept models)
                "refmod_1": ("STRING", {"default": "None", "tooltip": "RefMod name or relative path in models/refmods/."}),
                "refmod_2": ("STRING", {"default": "None", "tooltip": "RefMod 2."}),
            },
        }

    RETURN_TYPES = (MMX_REF_PACK,)
    RETURN_NAMES = ("ref_pack",)
    FUNCTION = "pack"
    CATEGORY = CATEGORY
    DESCRIPTION = "Pools image, video, audio, and RefMod references into a unified pack. Clips in MiniMax H3 Master Director locally select only the references they need."

    def pack(
        self,
        ref_pack_optional: Optional[Dict[str, Any]] = None,
        image_1: Optional[torch.Tensor] = None,
        image_2: Optional[torch.Tensor] = None,
        image_3: Optional[torch.Tensor] = None,
        image_4: Optional[torch.Tensor] = None,
        video_1: Optional[torch.Tensor] = None,
        video_2: Optional[torch.Tensor] = None,
        audio_1: Optional[Dict[str, Any]] = None,
        audio_2: Optional[Dict[str, Any]] = None,
        refmod_1: str = "None",
        refmod_2: str = "None",
        **kwargs,
    ):
        refs: List[Dict[str, Any]] = []

        # 1. Inherit from chained ref_pack if provided
        pack_index = 1
        if ref_pack_optional is not None and isinstance(ref_pack_optional, dict):
            existing = ref_pack_optional.get("refs", [])
            if isinstance(existing, list):
                refs.extend(existing)
            pack_index = int(ref_pack_optional.get("pack_count", 1)) + 1

        base_index = len(refs) + 1
        id_prefix = "" if pack_index == 1 else f"p{pack_index}_"

        # 2. Add image references
        img_slots = [
            (image_1, "image_1", "img_1"),
            (image_2, "image_2", "img_2"),
            (image_3, "image_3", "img_3"),
            (image_4, "image_4", "img_4"),
        ]
        for img, slot_name, alt_id in img_slots:
            if img is not None:
                assigned_id = f"{id_prefix}{slot_name}"
                refs.append({
                    "id": assigned_id,
                    "slot_id": slot_name,
                    "alt_id": f"{id_prefix}{alt_id}",
                    "ref_id": f"ref_{slot_name}_{base_index}",
                    "pack_index": pack_index,
                    "name": assigned_id,
                    "type": "image",
                    "data": img,
                })
                base_index += 1

        # 3. Add video references
        vid_slots = [
            (video_1, "video_1", "vid_1"),
            (video_2, "video_2", "vid_2"),
        ]
        for vid, slot_name, alt_id in vid_slots:
            if vid is not None:
                assigned_id = f"{id_prefix}{slot_name}"
                refs.append({
                    "id": assigned_id,
                    "slot_id": slot_name,
                    "alt_id": f"{id_prefix}{alt_id}",
                    "ref_id": f"ref_{slot_name}_{base_index}",
                    "pack_index": pack_index,
                    "name": assigned_id,
                    "type": "video",
                    "data": vid,
                })
                base_index += 1

        # 4. Add audio references
        aud_slots = [
            (audio_1, "audio_1", "aud_1"),
            (audio_2, "audio_2", "aud_2"),
        ]
        for aud, slot_name, alt_id in aud_slots:
            if aud is not None:
                assigned_id = f"{id_prefix}{slot_name}"
                refs.append({
                    "id": assigned_id,
                    "slot_id": slot_name,
                    "alt_id": f"{id_prefix}{alt_id}",
                    "ref_id": f"ref_{slot_name}_{base_index}",
                    "pack_index": pack_index,
                    "name": assigned_id,
                    "type": "audio",
                    "data": aud,
                })
                base_index += 1

        # 5. Add RefMod references (.safetensors character/concept models)
        mod_slots = [
            (refmod_1, "refmod_1", "mod_1"),
            (refmod_2, "refmod_2", "mod_2"),
        ]
        for mod, slot_name, alt_id in mod_slots:
            if mod is not None and str(mod).strip() and str(mod).strip().lower() != "none":
                assigned_id = f"{id_prefix}{slot_name}"
                refs.append({
                    "id": assigned_id,
                    "slot_id": slot_name,
                    "alt_id": f"{id_prefix}{alt_id}",
                    "ref_id": f"ref_{slot_name}_{base_index}",
                    "pack_index": pack_index,
                    "name": assigned_id,
                    "type": "refmod",
                    "data": str(mod).strip(),
                })
                base_index += 1

        pack = {
            "version": 1,
            "pack_count": pack_index,
            "refs": refs,
        }
        return (pack,)
