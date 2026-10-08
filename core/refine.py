"""Second-pass refinement, spatial tiled sampling, and latent upscaling for MiniMax H3 Master Director."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional


from .config import snap_to_multiple
from .sampling import sample_latent

log = logging.getLogger("MiniMaxH3MasterDirector.refine")


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
    tile_overlap: int = 128,
    sampler_name: str = "euler", scheduler: str = "simple", sigmas=None,
    passes: int = 1, latent_upscale_model=None, enable_chunking: bool = False,
    refine_backend="sampler", memory_budget_mb=0, video_vae=None,
    first_frame=None, last_frame=None, upscale_precision="auto",
) -> Dict[str, Any]:
    """Execute second-pass refine, upscale, or spatial tiled refinement."""
    if not 1 <= int(passes) <= 20:
        raise ValueError("Refine passes must be between 1 and 20.")
    active_model = refine_model if refine_model is not None else model

    from .continuity import unpack_av_samples, extract_streams_from_av_latent
    video, audio = extract_streams_from_av_latent(latent_dict)

    if refine_backend == "global":
        from .vendor.dasiwa.nodes_minimax_h3_tiled_upscale import DaSiWaH3TiledUpscale
        target_w = target_width if refine_mode in ("upscale", "latent_upscale") else video.shape[-1]*16
        target_h = target_height if refine_mode in ("upscale", "latent_upscale") else video.shape[-2]*16
        result = dict(latent_dict)
        prefix_tokens = int(latent_dict.get("_director_continue_prefix_steps", 0))
        continuity = None
        if prefix_tokens > 0:
            mask_streams, _ = unpack_av_samples(latent_dict.get("noise_mask"))
            audio_tokens = 0
            if len(mask_streams) > 1:
                # The continuation engine supplies the exact native audio phase.
                audio_mask = mask_streams[1]
                pinned = (audio_mask.reshape(-1, audio_mask.shape[-1]).amin(0) < 1).nonzero()
                if pinned.numel(): audio_tokens = int(pinned[-1].item()) + 1
            continuity = {"refine_start_token": max(0, prefix_tokens-1),
                "guide_start_token": 0,
                "source_tokens": prefix_tokens, "frame_offset": 0,
                "audio_start": 0, "source_audio_tokens": audio_tokens,
                "explanation": "phase-aligned continuation prefix retained; seam token may refine"}
        # Sampling has finished; the subsequent refine owns its own AV masks.
        result.pop("noise_mask", None)
        for index in range(int(passes)):
            result, report = DaSiWaH3TiledUpscale().upscale(active_model, positive, result,
                scale=1., upscale_model=latent_upscale_model or "interpolation",
                steps=steps, denoise=0. if refine_mode == "latent_upscale" else denoise,
                seed=seed+index, vae=video_vae, start_image=first_frame,
                director_guide={"first_frame": first_frame, "last_frame": last_frame},
                negative=negative, cfg=cfg, sampler_name=sampler_name, scheduler=scheduler,
                memory_budget_mb=memory_budget_mb, spatial_tiling=enable_tiling,
                temporal_chunking=enable_chunking, target_width=target_w, target_height=target_h,
                external_sigmas=sigmas, upscale_precision=upscale_precision,
                continuity_context=continuity, continuity_soft_refine=continuity is not None)
            result["_mmx_refine_report"] = report
            if refine_mode == "latent_upscale": break
        return result
    if refine_backend != "sampler":
        raise ValueError("Unknown refinement backend.")

    if refine_mode in ("upscale", "latent_upscale") and target_width and target_height:
        # Spatial upscale of video latent
        lat_h = snap_to_multiple(target_height // 16, 2)
        lat_w = snap_to_multiple(target_width // 16, 2)
        from .latent_utils import spatial_interpolate_video_latent
        old_hw = video.shape[-2:]
        if latent_upscale_model:
            from .vendor.aimixer.director.h3_latent_upscale import upscale_h3_video_latent
            video = upscale_h3_video_latent({"samples": video}, target_width=target_width, target_height=target_height,
                source_width=old_hw[1] * 16, source_height=old_hw[0] * 16,
                model_name=latent_upscale_model if isinstance(latent_upscale_model, str) else "",
                model=None if isinstance(latent_upscale_model, str) else latent_upscale_model,
                enable_latent_chunking=enable_chunking)["samples"]
        else:
            video = spatial_interpolate_video_latent(video, lat_h, lat_w)
        from .advanced_sampling import resize_conditioning
        positive = resize_conditioning(positive, old_hw, (lat_h, lat_w))
        negative = resize_conditioning(negative, old_hw, (lat_h, lat_w))

        try:
            import comfy.nested_tensor
            samples = comfy.nested_tensor.NestedTensor(tuple([video, audio]))
        except Exception:
            samples = tuple([video, audio])

        latent_dict = {**latent_dict, "samples": samples}

    if refine_mode == "latent_upscale":
        # No sampling pass requested; return upscaled latents directly
        return latent_dict

    for pass_index in range(int(passes)):
        log.info("Refine %s pass %d/%d", refine_mode, pass_index + 1, passes)
        if enable_tiling:
            from .advanced_sampling import sample_stage
            latent_dict = sample_stage(active_model, latent_dict, steps, cfg,
                sampler_name, scheduler, positive, negative, seed + pass_index,
                denoise, sigmas=sigmas, tile_count=tile_count, tile_overlap=tile_overlap)
        else:
            latent_dict = sample_latent(active_model, latent_dict, steps, cfg,
                sampler_name, scheduler, positive, negative, seed + pass_index,
                denoise=denoise, sigmas=sigmas)
    return latent_dict
