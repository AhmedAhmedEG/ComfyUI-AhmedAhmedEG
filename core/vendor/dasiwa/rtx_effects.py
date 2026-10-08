"""Selected RTX effect lifecycle helpers, DaSiWa GPL-3.0; see LICENSE."""
import torch
import contextlib
import math
import logging
def log_dasiwa(component, message):
    logging.getLogger("MiniMaxH3.RTX").info("%s: %s",component,message)

def _quality_attr(mode: str, quality: str) -> str:
    """Maps UI strings to nvvfx QualityLevel attributes."""
    q = quality.upper()
    if mode == "High Bitrate":
        return f"HIGHBITRATE_{q}"
    elif mode in ["Denoise", "Deblur"]:
        return f"{mode.upper()}_{q}"
    return q  # Default VSR

def _fit_frame_to_target_aspect(frame, target_width: int, target_height: int, resize_method: str):
    _, source_height, source_width = frame.shape
    source_aspect = float(source_width) / float(source_height)
    target_aspect = float(target_width) / float(target_height)
    ratio_width, ratio_height = _aspect_ratio_parts(target_width, target_height)

    if _same_aspect(source_width, source_height, target_width, target_height):
        return frame.contiguous()

    if resize_method == "Center Crop (Fill)":
        ratio_scale = min(int(source_width) // ratio_width, int(source_height) // ratio_height)
        if ratio_scale > 0:
            crop_width = ratio_scale * ratio_width
            crop_height = ratio_scale * ratio_height
        elif source_aspect > target_aspect:
            crop_width = max(1, min(int(source_width), int(round(float(source_height) * target_aspect))))
            crop_height = int(source_height)
        else:
            crop_width = int(source_width)
            crop_height = max(1, min(int(source_height), int(round(float(source_width) / target_aspect))))
        crop_x = max(0, (int(source_width) - crop_width) // 2)
        crop_y = max(0, (int(source_height) - crop_height) // 2)
        return frame[:, crop_y:crop_y + crop_height, crop_x:crop_x + crop_width].contiguous()

    # Letterbox (Fit)
    ratio_scale = max(
        math.ceil(int(source_width) / ratio_width),
        math.ceil(int(source_height) / ratio_height),
    )
    padded_width = max(int(source_width), ratio_scale * ratio_width)
    padded_height = max(int(source_height), ratio_scale * ratio_height)
    pad_width = padded_width - int(source_width)
    pad_height = padded_height - int(source_height)
    pad_left = pad_width // 2
    pad_right = pad_width - pad_left
    pad_top = pad_height // 2
    pad_bottom = pad_height - pad_top
    return F.pad(frame, (pad_left, pad_right, pad_top, pad_bottom), mode="constant", value=0.0).contiguous()

def _aspect_ratio_parts(width: int, height: int) -> Tuple[int, int]:
    divisor = math.gcd(int(width), int(height))
    if divisor <= 0:
        return max(1, int(width)), max(1, int(height))
    return max(1, int(width) // divisor), max(1, int(height) // divisor)

def _same_aspect(source_width: int, source_height: int, target_width: int, target_height: int) -> bool:
    return int(source_width) * int(target_height) == int(target_width) * int(source_height)

def _import_vfx():
    try:
        import nvvfx
    except ImportError:
        raise RuntimeError(
            "NVIDIA RTX VFX (nvvfx) module not found. "
            "Please ensure NVIDIA RTX Video SDK / Broadcast SDK is installed and the 'nvvfx' package is in your python path."
        )

    VideoSuperRes = getattr(nvvfx, "VideoSuperRes", None)
    if VideoSuperRes is None:
        try:
            from nvvfx import VideoSuperRes
        except ImportError as exc:
            raise RuntimeError("NVIDIA RTX VFX is installed, but VideoSuperRes is unavailable.") from exc

    effects = getattr(nvvfx, "effects", None)
    QualityLevel = getattr(effects, "QualityLevel", None)
    if QualityLevel is None:
        QualityLevel = getattr(VideoSuperRes, "QualityLevel", None)
    if QualityLevel is None:
        raise RuntimeError("NVIDIA RTX VFX VideoSuperRes quality levels are unavailable.")

    return VideoSuperRes, QualityLevel

def _resolve_quality_level(QualityLevel, mode: str, quality: str):
    attr_name = _quality_attr(mode, quality)
    q = quality.upper()
    candidates = [attr_name]
    if mode == "High Bitrate":
        candidates.extend([f"HIGH_BITRATE_{q}", f"HIGHBITRATE{q}"])
    elif mode == "VSR":
        candidates.append(q)

    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if hasattr(QualityLevel, candidate):
            return getattr(QualityLevel, candidate), candidate

    available = ", ".join(name for name in dir(QualityLevel) if name.isupper()) or "none"
    raise ValueError(
        f"Invalid or unsupported NVIDIA RTX VFX quality level '{attr_name}'. "
        f"Available levels: {available}"
    )

def _create_vfx_effect(VideoSuperRes, q_level, device_index: int):
    attempts = (
        ((), {"quality": q_level, "device": device_index}),
        ((q_level,), {"device": device_index}),
        ((), {"quality": q_level}),
        ((q_level,), {}),
    )
    last_type_error = None
    for args, kwargs in attempts:
        try:
            return VideoSuperRes(*args, **kwargs)
        except TypeError as exc:
            last_type_error = exc

    raise last_type_error

def _close_vfx_effect(effect):
    for method_name in ("close", "destroy", "unload"):
        method = getattr(effect, method_name, None)
        if callable(method):
            method()
            return

def _run_vfx_effect(effect, frame, cuda_device):
    if not frame.is_contiguous():
        frame = frame.contiguous()

    # nvvfx owns its execution stream and may reuse output buffers. Synchronize
    # before and after each handoff, then clone the DLPack tensor so the next
    # effect/frame cannot overwrite data that has not been assembled yet.
    torch.cuda.current_stream(cuda_device).synchronize()
    res = effect.run(frame)
    torch.cuda.synchronize(cuda_device)
    return torch.from_dlpack(res.image).clone().contiguous()

@contextlib.contextmanager
def _maybe_vfx_effect(vfx_api, enabled, mode, quality, device_index, out_width, out_height):
    if not enabled:
        yield None
        return

    VideoSuperRes, QualityLevel = vfx_api
    try:
        q_level, attr_name = _resolve_quality_level(QualityLevel, mode, quality)
    except AttributeError:
        raise ValueError(f"Invalid quality level mapping: {_quality_attr(mode, quality)}")

    effect_cm = None
    effect = None
    try:
        effect = _create_vfx_effect(VideoSuperRes, q_level, device_index)
        if hasattr(effect, "__enter__") and hasattr(effect, "__exit__"):
            effect_cm = effect
            effect = effect_cm.__enter__()
        effect.output_width = int(out_width)
        effect.output_height = int(out_height)
        if hasattr(effect, "load"):
            effect.load()
    except Exception as exc:
        if effect_cm is not None:
            effect_cm.__exit__(None, None, None)
        elif effect is not None:
            _close_vfx_effect(effect)
        raise RuntimeError(f"Failed to create NVIDIA RTX VFX effect ({mode} {attr_name}): {exc}")

    try:
        yield effect
    finally:
        if effect_cm is not None:
            effect_cm.__exit__(None, None, None)
        elif effect is not None:
            _close_vfx_effect(effect)
