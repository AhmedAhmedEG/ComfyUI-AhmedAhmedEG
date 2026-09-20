"""DaSiWa RTX Upscaler & Refiner node for high-performance video upscaling and refinement."""

from __future__ import annotations

import contextlib
import gc
import math
import os
from typing import Any, Dict, List, Optional, Tuple
import torch
import torch.nn.functional as F

QUALITY_LEVELS = ["Low", "Medium", "High", "Ultra"]
UPSCALE_MODES = ["Off", "VSR", "High Bitrate"]
RESIZE_TYPES = ["Keep Ratio", "Manual", "Preset Ratio", "Scale", "Same Size"]
DIVISIBLE_BY_VALUES = ["8", "16", "32", "64", "128"]
COMMON_RATIOS = ["1:1", "4:3", "3:2", "16:9", "21:9"]
RESIZE_METHODS = ["Center Crop (Fill)", "Letterbox (Fit)"]


def _calculate_target_resolution(
    orig_w: int,
    orig_h: int,
    resize_type: str,
    scale: float,
    megapixels: float,
    manual_w: int,
    manual_h: int,
    divisible_by: int,
    ratio_preset: str,
) -> Tuple[int, int]:
    if resize_type == "Same Size":
        tw, th = orig_w, orig_h
    elif resize_type == "Scale":
        tw, th = int(round(orig_w * scale)), int(round(orig_h * scale))
    elif resize_type == "Manual":
        tw, th = manual_w, manual_h
    elif resize_type == "Keep Ratio":
        target_pixels = megapixels * 1_000_000
        aspect = orig_w / max(1, orig_h)
        th = int(math.sqrt(target_pixels / aspect))
        tw = int(th * aspect)
    elif resize_type == "Preset Ratio":
        target_pixels = megapixels * 1_000_000
        parts = [float(p) for p in ratio_preset.split(":")]
        aspect = parts[0] / parts[1]
        th = int(math.sqrt(target_pixels / aspect))
        tw = int(th * aspect)
    else:
        tw, th = orig_w, orig_h

    # Snap to divisible_by
    tw = max(divisible_by, int(round(tw / divisible_by)) * divisible_by)
    th = max(divisible_by, int(round(th / divisible_by)) * divisible_by)
    return tw, th


def _import_vfx():
    try:
        import nvvfx
    except ImportError:
        return None, None

    VideoSuperRes = getattr(nvvfx, "VideoSuperRes", None)
    if VideoSuperRes is None:
        try:
            from nvvfx import VideoSuperRes
        except ImportError:
            return None, None

    effects = getattr(nvvfx, "effects", None)
    QualityLevel = getattr(effects, "QualityLevel", None) or getattr(VideoSuperRes, "QualityLevel", None)
    return VideoSuperRes, QualityLevel


def _resolve_quality_level(QualityLevel, mode: str, quality: str):
    if QualityLevel is None:
        return None
    q = quality.upper()
    candidates = [f"{mode.upper()}_{q}", f"{mode.upper()}{q}", q]
    if mode == "High Bitrate":
        candidates.extend([f"HIGH_BITRATE_{q}", f"HIGHBITRATE{q}"])
    for c in candidates:
        if hasattr(QualityLevel, c):
            return getattr(QualityLevel, c)
    return getattr(QualityLevel, "ULTRA", None) or getattr(QualityLevel, "HIGH", None)


class DaSiWa_RTX_UpscalerRefiner:
    """RTX video upscaler and refiner node supporting RTX VSR and high quality PyTorch interpolation."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", {"description": "Input image or video batch to process."}),
                "denoise": ("BOOLEAN", {"default": False, "description": "Enable Denoise pass."}),
                "denoise_quality": (QUALITY_LEVELS, {"default": "Ultra"}),
                "deblur": ("BOOLEAN", {"default": False, "description": "Enable Deblur pass."}),
                "deblur_quality": (QUALITY_LEVELS, {"default": "Ultra"}),
                "upscale": (UPSCALE_MODES, {"default": "VSR"}),
                "upscale_quality": (QUALITY_LEVELS, {"default": "Ultra"}),
                "resize_type": (RESIZE_TYPES, {"default": "Scale"}),
                "scale": ("FLOAT", {"default": 2.0, "min": 1.0, "max": 4.0, "step": 0.05}),
                "megapixels": ("FLOAT", {"default": 2.0, "min": 0.01, "max": 64.0, "step": 0.01}),
                "width": ("INT", {"default": 1920, "min": 64, "max": 8192, "step": 8}),
                "height": ("INT", {"default": 1080, "min": 64, "max": 8192, "step": 8}),
                "divisible_by": (DIVISIBLE_BY_VALUES, {"default": "8"}),
                "ratio_preset": (COMMON_RATIOS, {"default": "16:9"}),
                "resize_method": (RESIZE_METHODS, {"default": "Center Crop (Fill)"}),
                "device_id": ("INT", {"default": 0, "min": 0, "max": 8, "step": 1}),
            },
            "optional": {
                "empty_cache": ("BOOLEAN", {"default": False}),
                "use_mmap": ("BOOLEAN", {"default": False}),
                "auto_unload_models": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "execute"
    CATEGORY = "ComfyUI-AhmedAhmedEG"

    def execute(
        self,
        images,
        denoise=False,
        denoise_quality="Ultra",
        deblur=False,
        deblur_quality="Ultra",
        upscale="VSR",
        upscale_quality="Ultra",
        resize_type="Scale",
        scale=2.0,
        megapixels=2.0,
        width=1920,
        height=1080,
        divisible_by="8",
        ratio_preset="16:9",
        resize_method="Center Crop (Fill)",
        device_id=0,
        **kwargs,
    ):
        if images is None or images.shape[0] == 0:
            return (images,)

        div = int(divisible_by)
        orig_h, orig_w = images.shape[1], images.shape[2]
        target_w, target_h = _calculate_target_resolution(
            orig_w, orig_h, resize_type, scale, megapixels, width, height, div, ratio_preset
        )

        upscale_enabled = upscale != "Off"
        if not (denoise or deblur or upscale_enabled):
            return (images,)

        # Try RTX Video SDK if available
        vfx_applied = False
        if torch.cuda.is_available():
            try:
                VideoSuperRes, QualityLevel = _import_vfx()
                if VideoSuperRes is not None and QualityLevel is not None:
                    cuda_device = torch.device(f"cuda:{device_id}")
                    q_level = _resolve_quality_level(QualityLevel, upscale, upscale_quality)
                    
                    # Instantiate effect
                    try:
                        effect = VideoSuperRes(quality=q_level, device=device_id)
                    except TypeError:
                        effect = VideoSuperRes(q_level)

                    effect.output_width = int(target_w)
                    effect.output_height = int(target_h)
                    if hasattr(effect, "load"):
                        effect.load()

                    out_frames = []
                    b = images.shape[0]
                    with torch.cuda.device(cuda_device), torch.inference_mode():
                        for i in range(b):
                            frame = images[i : i + 1, :, :, :3].to(device=cuda_device, dtype=torch.float32).contiguous()
                            torch.cuda.current_stream(cuda_device).synchronize()
                            res = effect.run(frame)
                            torch.cuda.synchronize(cuda_device)
                            res_tensor = torch.from_dlpack(res.image).clone().contiguous().cpu()
                            out_frames.append(res_tensor)

                    if hasattr(effect, "close"):
                        effect.close()
                    elif hasattr(effect, "destroy"):
                        effect.destroy()

                    if out_frames:
                        return (torch.cat(out_frames, dim=0),)
            except Exception:
                # Graceful fallback to high quality PyTorch interpolation
                vfx_applied = False

        if not vfx_applied:
            # High-quality PyTorch interpolation fallback
            b = images.shape[0]
            chunk_size = 16
            output_list = []
            for i in range(0, b, chunk_size):
                chunk = images[i : i + chunk_size].permute(0, 3, 1, 2)  # [B, C, H, W]
                resized = F.interpolate(
                    chunk,
                    size=(target_h, target_w),
                    mode="bicubic",
                    align_corners=False,
                    antialias=True,
                )
                output_list.append(resized.permute(0, 2, 3, 1).clamp(0.0, 1.0).cpu())

            out_tensor = torch.cat(output_list, dim=0)
            return (out_tensor,)

        return (images,)
