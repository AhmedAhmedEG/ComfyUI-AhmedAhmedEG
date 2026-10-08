"""Graph pack for Director.face_refine. Unconnected → None, zero execute impact."""


from __future__ import annotations


from typing import Any


SELECT_MODES = ("largest_face", "centre_most")


CANVAS_MODES = ("manual", "auto_capped_768")


PASTE_REGIONS = ("face_only", "face_ellipse", "full_crop")


SEED_MODES = ("inherit", "offset")


DEFAULT_DETECTOR = "face_yolov8m.pt"


DEFAULT_SAMPLER = "euler"


DEFAULT_SCHEDULER = "simple"


def _clamp_int(raw: Any, lo: int, hi: int, default: int) -> int:
    try:
        n = int(raw)
    except (TypeError, ValueError):
        n = default
    return max(lo, min(hi, n))


def _clamp_float(raw: Any, lo: float, hi: float, default: float) -> float:
    try:
        n = float(raw)
    except (TypeError, ValueError):
        n = default
    return max(lo, min(hi, n))


def pack_face_refine(
    *,
    detector: str = DEFAULT_DETECTOR,
    confidence: float = 0.35,
    crop_factor: float = 2.5,
    canvas_width: int = 768,
    canvas_height: int = 768,
    canvas_mode: str = "manual",
    select: str = "largest_face",
    denoise: float = 0.40,
    steps: int = 8,
    sampler: str = DEFAULT_SAMPLER,
    scheduler: str = DEFAULT_SCHEDULER,
    seed_mode: str = "inherit",
    paste_region: str = "face_only",
    mask_dilation: int = 16,
    feather: int = 24,
    colour_match: float = 1.0,
    blend: float = 1.0,
    sigmas=None,
) -> dict[str, Any]:
    mode = str(canvas_mode or "manual").strip().lower()
    if mode not in CANVAS_MODES:
        mode = "manual"
    sel = str(select or "largest_face").strip().lower()
    if sel not in SELECT_MODES:
        sel = "largest_face"
    paste = str(paste_region or "face_only").strip().lower()
    if paste not in PASTE_REGIONS:
        paste = "face_only"
    seed = str(seed_mode or "inherit").strip().lower()
    if seed not in SEED_MODES:
        seed = "inherit"
    from ...lib.image_prep import ensure_minimax_canvas
    from ..refine_pack import is_refine_sigmas_tensor, parse_refine_sigmas

    sigma_tensor = sigmas if is_refine_sigmas_tensor(sigmas) else None
    parsed = (
        parse_refine_sigmas(sigma_tensor, fallback=False) if sigma_tensor is not None else ()
    )
    canvas_width, canvas_height = ensure_minimax_canvas(
        _clamp_int(canvas_width, 128, 1344, 768),
        _clamp_int(canvas_height, 128, 1344, 768),
    )
    return {
        "enabled": True,
        "detector": str(detector or DEFAULT_DETECTOR).strip() or DEFAULT_DETECTOR,
        "confidence": _clamp_float(confidence, 0.05, 0.95, 0.35),
        "crop_factor": _clamp_float(crop_factor, 1.2, 8.0, 2.5),
        "canvas_width": int(canvas_width),
        "canvas_height": int(canvas_height),
        "canvas_mode": mode,
        "select": sel,
        "denoise": _clamp_float(denoise, 0.02, 1.0, 0.40),
        "steps": _clamp_int(steps, 1, 50, 8),
        "sampler": str(sampler or DEFAULT_SAMPLER).strip() or DEFAULT_SAMPLER,
        "scheduler": str(scheduler or DEFAULT_SCHEDULER).strip() or DEFAULT_SCHEDULER,
        "seed_mode": seed,
        "paste_region": paste,
        "mask_dilation": _clamp_int(mask_dilation, 0, 256, 16),
        "feather": _clamp_int(feather, 0, 256, 24),
        "colour_match": _clamp_float(colour_match, 0.0, 1.0, 1.0),
        "blend": _clamp_float(blend, 0.0, 1.0, 1.0),
        "sigmas": ",".join(f"{x:g}" for x in parsed),
        "sigmas_parsed": parsed,
        "sigmas_tensor": sigma_tensor,
        "has_sigmas_tensor": sigma_tensor is not None,
    }
