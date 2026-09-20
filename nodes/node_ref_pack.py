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
                "label_img_1": ("STRING", {"default": "Character 1", "tooltip": "Label to display in timeline clip inspector."}),
                "image_2": ("IMAGE", {"tooltip": "Reference image 2."}),
                "label_img_2": ("STRING", {"default": "Character 2", "tooltip": "Label to display in timeline clip inspector."}),
                "image_3": ("IMAGE", {"tooltip": "Reference image 3."}),
                "label_img_3": ("STRING", {"default": "Setting / Environment", "tooltip": "Label to display in timeline clip inspector."}),
                "image_4": ("IMAGE", {"tooltip": "Reference image 4."}),
                "label_img_4": ("STRING", {"default": "Prop / Object", "tooltip": "Label to display in timeline clip inspector."}),

                # Video references
                "video_1": ("IMAGE", {"tooltip": "Reference video 1 (frame batch) for V2V / RV2V. Referred as <Video 1> in prompts."}),
                "label_vid_1": ("STRING", {"default": "Video 1", "tooltip": "Label to display in timeline clip inspector."}),
                "video_2": ("IMAGE", {"tooltip": "Reference video 2 (frame batch). Referred as <Video 2> in prompts."}),
                "label_vid_2": ("STRING", {"default": "Video 2", "tooltip": "Label to display in timeline clip inspector."}),

                # Audio references
                "audio_1": ("AUDIO", {"tooltip": "Reference audio 1 (e.g. speech, music, soundscape). Referred as <Audio 1> in prompts."}),
                "label_aud_1": ("STRING", {"default": "Dialogue 1", "tooltip": "Label to display in timeline clip inspector."}),
                "audio_2": ("AUDIO", {"tooltip": "Reference audio 2. Referred as <Audio 2> in prompts."}),
                "label_aud_2": ("STRING", {"default": "Soundtrack 1", "tooltip": "Label to display in timeline clip inspector."}),

                # RefMod references (.safetensors character/concept models)
                "refmod_1": ("STRING", {"default": "None", "tooltip": "RefMod name or relative path in models/refmods/."}),
                "label_mod_1": ("STRING", {"default": "Character Concept 1", "tooltip": "Label to display in timeline clip inspector."}),
                "refmod_2": ("STRING", {"default": "None", "tooltip": "RefMod 2."}),
                "label_mod_2": ("STRING", {"default": "Character Concept 2", "tooltip": "Label to display in timeline clip inspector."}),
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
        label_img_1: str = "Character 1",
        image_2: Optional[torch.Tensor] = None,
        label_img_2: str = "Character 2",
        image_3: Optional[torch.Tensor] = None,
        label_img_3: str = "Setting / Environment",
        image_4: Optional[torch.Tensor] = None,
        label_img_4: str = "Prop / Object",
        video_1: Optional[torch.Tensor] = None,
        label_vid_1: str = "Video 1",
        video_2: Optional[torch.Tensor] = None,
        label_vid_2: str = "Video 2",
        audio_1: Optional[Dict[str, Any]] = None,
        label_aud_1: str = "Dialogue 1",
        audio_2: Optional[Dict[str, Any]] = None,
        label_aud_2: str = "Soundtrack 1",
        refmod_1: str = "None",
        label_mod_1: str = "Character Concept 1",
        refmod_2: str = "None",
        label_mod_2: str = "Character Concept 2",
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
            (image_1, label_img_1, "img_1"),
            (image_2, label_img_2, "img_2"),
            (image_3, label_img_3, "img_3"),
            (image_4, label_img_4, "img_4"),
        ]
        for img, lbl, slot_id in img_slots:
            if img is not None:
                name = lbl.strip() if lbl and lbl.strip() else f"Image {base_index}"
                assigned_id = f"{id_prefix}{slot_id}"
                refs.append({
                    "id": assigned_id,
                    "slot_id": slot_id,
                    "ref_id": f"ref_{slot_id}_{base_index}",
                    "pack_index": pack_index,
                    "name": name,
                    "type": "image",
                    "data": img,
                })
                base_index += 1

        # 3. Add video references
        vid_slots = [
            (video_1, label_vid_1, "vid_1"),
            (video_2, label_vid_2, "vid_2"),
        ]
        for vid, lbl, slot_id in vid_slots:
            if vid is not None:
                name = lbl.strip() if lbl and lbl.strip() else f"Video {base_index}"
                assigned_id = f"{id_prefix}{slot_id}"
                refs.append({
                    "id": assigned_id,
                    "slot_id": slot_id,
                    "ref_id": f"ref_{slot_id}_{base_index}",
                    "pack_index": pack_index,
                    "name": name,
                    "type": "video",
                    "data": vid,
                })
                base_index += 1

        # 4. Add audio references
        aud_slots = [
            (audio_1, label_aud_1, "aud_1"),
            (audio_2, label_aud_2, "aud_2"),
        ]
        for aud, lbl, slot_id in aud_slots:
            if aud is not None:
                name = lbl.strip() if lbl and lbl.strip() else f"Audio {base_index}"
                assigned_id = f"{id_prefix}{slot_id}"
                refs.append({
                    "id": assigned_id,
                    "slot_id": slot_id,
                    "ref_id": f"ref_{slot_id}_{base_index}",
                    "pack_index": pack_index,
                    "name": name,
                    "type": "audio",
                    "data": aud,
                })
                base_index += 1

        # 5. Add RefMod references (.safetensors character/concept models)
        mod_slots = [
            (refmod_1, label_mod_1, "mod_1"),
            (refmod_2, label_mod_2, "mod_2"),
        ]
        for mod, lbl, slot_id in mod_slots:
            if mod is not None and str(mod).strip() and str(mod).strip().lower() != "none":
                name = lbl.strip() if lbl and lbl.strip() else f"RefMod {base_index}"
                assigned_id = f"{id_prefix}{slot_id}"
                refs.append({
                    "id": assigned_id,
                    "slot_id": slot_id,
                    "ref_id": f"ref_{slot_id}_{base_index}",
                    "pack_index": pack_index,
                    "name": name,
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
