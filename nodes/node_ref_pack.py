"""MiniMax H3 Reference Pack (RefPool) Node.

Provides an unlimited pool of image, video, and audio references for timeline clips.
Clips on the timeline locally select which references they use, preventing global contamination.
"""

from __future__ import annotations

import logging
import math
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

                "image_1_name": ("STRING", {"default": "", "tooltip": "Optional display name for image_1. Does not change reference tokens or IDs."}),
                "image_2_name": ("STRING", {"default": "", "tooltip": "Optional display name for image_2. Does not change reference tokens or IDs."}),
                "image_3_name": ("STRING", {"default": "", "tooltip": "Optional display name for image_3. Does not change reference tokens or IDs."}),
                "image_4_name": ("STRING", {"default": "", "tooltip": "Optional display name for image_4. Does not change reference tokens or IDs."}),
                "video_1_name": ("STRING", {"default": "", "tooltip": "Optional display name for video_1. Does not change reference tokens or IDs."}),
                "video_2_name": ("STRING", {"default": "", "tooltip": "Optional display name for video_2. Does not change reference tokens or IDs."}),
                "audio_1_name": ("STRING", {"default": "", "tooltip": "Optional display name for audio_1. Does not change reference tokens or IDs."}),
                "audio_2_name": ("STRING", {"default": "", "tooltip": "Optional display name for audio_2. Does not change reference tokens or IDs."}),
                "refmod_1_name": ("STRING", {"default": "", "tooltip": "Optional display name for refmod_1. Does not change reference tokens or IDs."}),
                "refmod_2_name": ("STRING", {"default": "", "tooltip": "Optional display name for refmod_2. Does not change reference tokens or IDs."}),
                # Image references
                "image_1": ("IMAGE", {"tooltip": "Reference image 1 (e.g. character, style, face, start frame)."}),
                "image_2": ("IMAGE", {"tooltip": "Reference image 2."}),
                "image_3": ("IMAGE", {"tooltip": "Reference image 3."}),
                "image_4": ("IMAGE", {"tooltip": "Reference image 4."}),

                # Video references
                "video_1": ("VIDEO,IMAGE", {"tooltip": "Native VIDEO or decoded IMAGE frame batch. Native videos supply their own FPS and audio."}),
                "video_2": ("VIDEO,IMAGE", {"tooltip": "Native VIDEO or decoded IMAGE frame batch."}),

                # Audio references
                "audio_1": ("AUDIO", {"tooltip": "Reference audio 1 (e.g. speech, music, soundscape)."}),
                "audio_2": ("AUDIO", {"tooltip": "Reference audio 2."}),

                # RefMod references (.safetensors character/concept models)
                "refmod_1": ("STRING", {"default": "None", "tooltip": "RefMod name or relative path in models/refmods/."}),
                "refmod_2": ("STRING", {"default": "None", "tooltip": "RefMod 2."}),
                "video_1_audio": ("AUDIO", {"tooltip": "Optional soundtrack paired with video_1. IMAGE frame batches contain no audio."}),
                "video_2_audio": ("AUDIO", {"tooltip": "Optional soundtrack paired with video_2."}),
                "video_1_fps": ("FLOAT", {"default":24.0,"min":1.0,"max":240.0,"tooltip":"Actual rate of video_1's frame batch. Match the loader's output rate; the pack resamples to H3's 24 fps."}),
                "video_2_fps": ("FLOAT", {"default":24.0,"min":1.0,"max":240.0,"tooltip":"Actual rate of video_2's frame batch. Match the loader's output rate."}),
                "asset_edits": ("STRING", {"default":"{}", "multiline":True, "tooltip":"Pack-owned trims, crop, roles and file references; edited in the asset panel."}),
                "refmod_library": ("MMX_REFMOD_LIBRARY", {"tooltip":"RefMod selections configured in the separate library node."}),
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
                    "name": str(kwargs.get(f"{slot_name}_name", "")).strip() or assigned_id,
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
                audio = kwargs.get(f"{slot_name}_audio")
                if callable(getattr(vid, "get_components", None)):
                    components = vid.get_components()
                    vid = components.images
                    fps = float(components.frame_rate)
                    if audio is None:
                        audio = components.audio
                else:
                    fps = float(kwargs.get(f"{slot_name}_fps", 24))
                if not math.isfinite(fps) or not 1 <= fps <= 240 or vid.ndim != 4 or vid.shape[0] == 0:
                    raise ValueError(f"{slot_name} needs a nonempty frame batch and an FPS between 1 and 240.")
                if fps != 24:
                    count = max(1, round(vid.shape[0] / fps * 24))
                    indices = torch.arange(count, device=vid.device).mul(fps / 24).long().clamp(max=vid.shape[0]-1)
                    vid = vid[indices]
                assigned_id = f"{id_prefix}{slot_name}"
                refs.append({
                    "id": assigned_id,
                    "slot_id": slot_name,
                    "alt_id": f"{id_prefix}{alt_id}",
                    "ref_id": f"ref_{slot_name}_{base_index}",
                    "pack_index": pack_index,
                    "name": str(kwargs.get(f"{slot_name}_name", "")).strip() or assigned_id,
                    "type": "video",
                    "data": vid,
                    "audio": audio,
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
                    "name": str(kwargs.get(f"{slot_name}_name", "")).strip() or assigned_id,
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
                    "name": str(kwargs.get(f"{slot_name}_name", "")).strip() or assigned_id,
                    "type": "refmod",
                    "data": str(mod).strip(),
                })
                base_index += 1

        try:
            from ..core.asset_editor import prepare_pack
        except ImportError:
            from core.asset_editor import prepare_pack
        local=refs[len(ref_pack_optional.get("refs",[])):] if ref_pack_optional else refs
        inherited=refs[:len(refs)-len(local)]
        import json
        edits=json.loads(kwargs.get("asset_edits","{}"))
        root=None
        if edits.get("files"):
            import folder_paths
            root=folder_paths.get_input_directory()
        local=prepare_pack(local,edits,root)
        for row in (kwargs.get("refmod_library") or {}).get("refs",[]):
            local.append({**row,"id":id_prefix+row["id"],"pack_index":pack_index})
        refs=inherited+local
        pack = {
            "version": 1,
            "pack_count": pack_index,
            "refs": refs,
        }
        return (pack,)
