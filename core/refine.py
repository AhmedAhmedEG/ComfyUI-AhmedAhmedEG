"""Second-pass refinement, spatial tiled sampling, and latent upscaling for MiniMax H3 Master Director."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn.functional as F

from .config import snap_to_multiple, CANVAS_MULTIPLE

log = logging.getLogger("MiniMaxH3MasterDirector.refine")


def spatial_tiled_sample(
    model,
    latent_dict: Dict[str, Any],
    steps: int,
    cfg: float,
    sampler_name: str,
    scheduler: str,
    positive,
    negative,
    seed: int,
    denoise: float = 0.5,
    tile_count: int = 2,
    tile_overlap: int = 128,
) -> Dict[str, Any]:
    """Sample large video latents across overlapping spatial tiles to prevent CUDA out-of-memory."""
    import comfy.sample

    if tile_count <= 1:
        return comfy.sample.sample(
            model, latent_dict, steps, cfg, sampler_name, scheduler, positive, negative, seed, denoise=denoise
        )

    samples = latent_dict["samples"]
    streams = list(samples.unbind() if hasattr(samples, "unbind") else samples)
    video = streams[0]  # [B, C, T, H, W]
    audio = streams[1]

    b, c, t, h, w = video.shape
    tile_w = snap_to_multiple((w + (tile_count - 1) * tile_overlap) // tile_count, 2)
    step_x = tile_w - tile_overlap

    accum = torch.zeros_like(video)
    weight = torch.zeros((1, 1, 1, 1, w), device=video.device, dtype=video.dtype)

    for i in range(tile_count):
        start_x = i * step_x
        if i == tile_count - 1:
            start_x = w - tile_w
        end_x = start_x + tile_w

        tile_video = video[:, :, :, :, start_x:end_x].clone()
        try:
            import comfy.nested_tensor
            tile_samples = comfy.nested_tensor.NestedTensor(tuple([tile_video, audio]))
        except Exception:
            tile_samples = tuple([tile_video, audio])

        tile_res = comfy.sample.sample(
            model, {"samples": tile_samples}, steps, cfg, sampler_name, scheduler, positive, negative, seed, denoise=denoise
        )
        res_video = (tile_res["samples"].unbind() if hasattr(tile_res["samples"], "unbind") else tile_res["samples"])[0]

        # Cosine ramp blend mask
        tile_mask = torch.ones((1, 1, 1, 1, tile_w), device=video.device, dtype=video.dtype)
        if i > 0 and tile_overlap > 0:
            tile_mask[:, :, :, :, :tile_overlap] = torch.linspace(0.0, 1.0, tile_overlap, device=video.device).view(1, 1, 1, 1, -1)
        if i < tile_count - 1 and tile_overlap > 0:
            tile_mask[:, :, :, :, -tile_overlap:] = torch.linspace(1.0, 0.0, tile_overlap, device=video.device).view(1, 1, 1, 1, -1)

        accum[:, :, :, :, start_x:end_x] += res_video * tile_mask
        weight[:, :, :, :, start_x:end_x] += tile_mask

    merged_video = accum / (weight + 1e-8)

    try:
        final_samples = comfy.nested_tensor.NestedTensor(tuple([merged_video, audio]))
    except Exception:
        final_samples = tuple([merged_video, audio])

    return {"samples": final_samples}


def apply_refine_pass(
    model,
    latent_dict: Dict[str, Any],
    positive,
    negative,
    seed: int,
    refine_mode: str = "refine",
    target_width: Optional[int] = None,
    target_height: Optional[int] = None,
    refine_model=None,
    steps: int = 3,
    cfg: float = 1.0,
    denoise: float = 0.45,
    enable_tiling: bool = False,
    tile_count: int = 2,
) -> Dict[str, Any]:
    """Execute second-pass refine, upscale, or spatial tiled refinement."""
    active_model = refine_model if refine_model is not None else model

    samples = latent_dict["samples"]
    streams = list(samples.unbind() if hasattr(samples, "unbind") else samples)
    video = streams[0]
    audio = streams[1]

    if refine_mode in ("upscale", "latent_upscale") and target_width and target_height:
        # Spatial upscale of video latent
        lat_h = snap_to_multiple(target_height // 16, 2)
        lat_w = snap_to_multiple(target_width // 16, 2)
        from .selflift import spatial_interpolate_video_latent
        video = spatial_interpolate_video_latent(video, lat_h, lat_w)

        try:
            import comfy.nested_tensor
            samples = comfy.nested_tensor.NestedTensor(tuple([video, audio]))
        except Exception:
            samples = tuple([video, audio])

        latent_dict = {"samples": samples}

    if refine_mode == "latent_upscale":
        # No sampling pass requested; return upscaled latents directly
        return latent_dict

    # Sample refine pass
    log.info(f"Refine: Running {refine_mode} pass ({steps} steps, denoise={denoise:.2f})...")
    if enable_tiling:
        return spatial_tiled_sample(
            active_model, latent_dict, steps, cfg, "euler", "simple", positive, negative, seed, denoise=denoise, tile_count=tile_count
        )

    import comfy.sample
    return comfy.sample.sample(
        active_model, latent_dict, steps, cfg, "euler", "simple", positive, negative, seed, denoise=denoise
    )
