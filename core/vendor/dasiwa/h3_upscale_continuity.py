"""Selected continuity conditioning adapter (DaSiWa, GPL-3.0)."""
from collections.abc import Mapping
import math

def align_continuity_conditioning(conditioning, upscaled_video, original_audio, plan, *, inject_tail=True):
    """Copy each entry, shift local guides, and optionally replace the native AV tail.

    Tensor slices are cloned for the new anchor; text, refs and unknown metadata
    keep their identities. No source tensor or incoming conditioning is mutated.
    """
    if plan is None:
        return conditioning
    if not isinstance(conditioning, (list, tuple)):
        raise TypeError("conditioning must be a ComfyUI conditioning sequence.")
    start, end = plan.get("guide_start_token", plan["refine_start_token"]), plan["source_tokens"]
    offset = plan["frame_offset"]
    result = []
    for entry in conditioning:
        if not isinstance(entry, (list, tuple)) or len(entry) < 2 or not isinstance(entry[1], Mapping):
            raise TypeError("conditioning entries must contain text and a metadata mapping.")
        metadata = dict(entry[1])
        incoming = metadata.get("minimax_keyframes", [])
        if not isinstance(incoming, (list, tuple)):
            raise TypeError("minimax_keyframes must be a sequence of mappings.")
        keyframes = []
        replaced = False
        for guide in incoming:
            if not isinstance(guide, Mapping):
                raise TypeError("Every MiniMax keyframe must be a mapping.")
            shifted = dict(guide)
            position = guide.get("resolved_frame_index")
            if isinstance(position, bool) or not isinstance(position, (int, float)) or not math.isfinite(position):
                raise ValueError("MiniMax keyframes require a finite resolved_frame_index.")
            shifted["resolved_frame_index"] = position + offset
            latent, audio = guide.get("latent"), guide.get("audio_latent")
            native_tail = (position == 0 and getattr(latent, "ndim", None) == 5
                           and latent.shape[2] == end - start
                           and getattr(audio, "ndim", None) == 4)
            if inject_tail and native_tail:
                shifted.update(latent=upscaled_video[:, :, start:end].clone(),
                               audio_latent=original_audio[..., plan["audio_start"]:plan["source_audio_tokens"]].clone())
                replaced = True
            keyframes.append(shifted)
        if inject_tail and not replaced:
            keyframes.append(dict(resolved_frame_index=offset,
                                  latent=upscaled_video[:, :, start:end].clone(),
                                  audio_latent=original_audio[..., plan["audio_start"]:plan["source_audio_tokens"]].clone()))
        if incoming or inject_tail or "minimax_keyframes" in metadata:
            metadata["minimax_keyframes"] = keyframes
        copied = list(entry)
        copied[1] = metadata
        result.append(tuple(copied) if isinstance(entry, tuple) else copied)
    return result
