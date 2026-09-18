"""Task mode definitions and validation logic for MiniMax H3 Master Director."""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple
from .config import (
    MAX_REF_IMAGES,
    MAX_REF_VIDEOS,
    MAX_REF_AUDIOS,
    MAX_TOTAL_REFS,
    MIN_REF_DURATION,
    MAX_REF_DURATION,
    MAX_REF_TOTAL_DURATION,
)

# Canonical mode names
MODE_T2VA = "T2VA"
MODE_I2VA = "I2VA"
MODE_FL2VA = "FL2VA"
MODE_L2VA = "L2VA"
MODE_REF2VA = "REF2VA"
MODE_V2V = "V2V"
MODE_RV2V = "RV2V"
MODE_INPAINT = "Image Inpaint"

SUPPORTED_MODES = (
    MODE_T2VA,
    MODE_I2VA,
    MODE_FL2VA,
    MODE_L2VA,
    MODE_REF2VA,
    MODE_V2V,
    MODE_RV2V,
    MODE_INPAINT,
)

# Keyframe-based modes (use FL2VA UNET: minimax_h3_fl2va_*)
KEYFRAME_MODES = {MODE_T2VA, MODE_I2VA, MODE_FL2VA, MODE_L2VA, MODE_INPAINT}

# Reference-based modes (use REF2VA UNET: minimax_h3_ref2va_*)
REFERENCE_MODES = {MODE_REF2VA, MODE_V2V, MODE_RV2V}


def normalize_mode(mode: str) -> str:
    """Normalize user or workflow mode string to canonical mode name."""
    m = str(mode or "").strip().upper()
    mapping = {
        "T2V": MODE_T2VA,
        "T2VA": MODE_T2VA,
        "I2V": MODE_I2VA,
        "I2VA": MODE_I2VA,
        "FL2V": MODE_FL2VA,
        "FL2VA": MODE_FL2VA,
        "L2V": MODE_L2VA,
        "L2VA": MODE_L2VA,
        "R2V": MODE_REF2VA,
        "REF2V": MODE_REF2VA,
        "REF2VA": MODE_REF2VA,
        "V2V": MODE_V2V,
        "RV2V": MODE_RV2V,
        "INPAINT": MODE_INPAINT,
        "IMAGE INPAINT": MODE_INPAINT,
    }
    return mapping.get(m, MODE_REF2VA)


def get_required_model_type(mode: str) -> str:
    """Return 'fl2va' or 'ref2va' depending on the active mode."""
    canon = normalize_mode(mode)
    return "fl2va" if canon in KEYFRAME_MODES else "ref2va"


def validate_mode_assets(
    mode: str,
    images: List[Any] | None = None,
    videos: List[Any] | None = None,
    audios: List[Any] | None = None,
    refmods: List[Any] | None = None,
    ref_video_durations: List[float] | None = None,
    raise_on_error: bool = False,
) -> Tuple[bool, List[str]]:
    """Validate asset limits and constraints for the selected mode.
    
    Returns (is_valid, list_of_error_messages).
    """
    canon = normalize_mode(mode)
    errors: List[str] = []
    
    img_count = len(images or [])
    vid_count = len(videos or [])
    aud_count = len(audios or [])
    mod_count = len(refmods or [])
    total_count = img_count + vid_count + aud_count + mod_count

    if canon == MODE_INPAINT:
        if img_count != 1:
            errors.append("Image Inpaint requires exactly one image reference.")
        if vid_count > 0 or aud_count > 0:
            errors.append("Image Inpaint accepts image references only (videos/audios are forbidden).")
        if raise_on_error and errors:
            raise ValueError("; ".join(errors))
        return len(errors) == 0, errors

    if canon in KEYFRAME_MODES:
        if vid_count > 0 or aud_count > 0:
            errors.append(f"{canon} mode accepts keyframe images only; videos and standalone audio clips are not allowed.")
        if canon == MODE_T2VA and img_count > 0:
            errors.append("T2VA is text-only; no images should be attached.")
        elif canon in (MODE_I2VA, MODE_L2VA) and img_count > 1:
            errors.append(f"{canon} accepts at most 1 keyframe image.")
        elif canon == MODE_FL2VA and img_count > 2:
            pass

    elif canon in REFERENCE_MODES:
        if img_count > MAX_REF_IMAGES:
            errors.append(f"REF2VA supports at most {MAX_REF_IMAGES} reference images (got {img_count}).")
        if vid_count > MAX_REF_VIDEOS:
            errors.append(f"REF2VA supports at most {MAX_REF_VIDEOS} reference videos (got {vid_count}).")
        if aud_count > MAX_REF_AUDIOS:
            errors.append(f"REF2VA supports at most {MAX_REF_AUDIOS} reference audios (got {aud_count}).")
        if total_count > MAX_TOTAL_REFS:
            errors.append(f"REF2VA supports at most {MAX_TOTAL_REFS} total reference files (got {total_count}).")
        if aud_count > 0 and img_count == 0 and vid_count == 0 and mod_count == 0:
            errors.append("REF2VA audio references must be accompanied by at least one visual reference (image, video, or RefMod).")
        if ref_video_durations:
            for d in ref_video_durations:
                if d > MAX_REF_DURATION:
                    errors.append(f"Reference video duration {d}s exceeds maximum {MAX_REF_DURATION}s.")
            if sum(ref_video_durations) > MAX_REF_TOTAL_DURATION:
                errors.append(f"Total reference video duration {sum(ref_video_durations)}s exceeds maximum {MAX_REF_TOTAL_DURATION}s.")

    if raise_on_error and errors:
        raise ValueError("; ".join(errors))

    return len(errors) == 0, errors
