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
    first_frame=None, last_frame=None, upscale_precision="auto", pass_callback=None,
    upscale_method="latent", upscale_model=None, spike_guard=False, guard_sensitivity=4.3, guard_strength=1.0,
    seed_policy="legacy", refine_seed_value="0", canvas_policy="manual", megapixels=1.8,
    resize_method="Stretch", guard_mode="burn_direction", memory_planning=True, memory_reserve_pct=35.0,
) -> Dict[str, Any]:
    """Execute second-pass refine, upscale, or spatial tiled refinement."""
    from .refine_controls import MAX_REFINE_PASSES, refine_seed, refine_canvas
    if not 1 <= int(passes) <= MAX_REFINE_PASSES:
        raise ValueError(f"Refine passes must be between 1 and {MAX_REFINE_PASSES}.")
    pass_seed=lambda index: refine_seed(seed,seed_policy,refine_seed_value,index)
    pass_seed(0)
    active_model = refine_model if refine_model is not None else model

    from .continuity import unpack_av_samples, extract_streams_from_av_latent
    video, audio = extract_streams_from_av_latent(latent_dict)
    if refine_mode in ('upscale','latent_upscale'):
        target_width,target_height=refine_canvas(video,canvas_policy,megapixels,target_width,target_height)

    if upscale_method not in ('latent','learned_pixel','RTX VSR','bicubic','lanczos'):
        raise ValueError('Unknown refine upscale method.')
    if spike_guard and (upscale_method!='latent' or not latent_upscale_model or refine_backend=='sampler' and refine_mode=='refine'):
        raise ValueError('Spike Guard requires a learned latent upscale model.')
    def resized_masks(data,new_hw):
        if data.get('noise_mask') is None:return data
        streams,_=unpack_av_samples(data['noise_mask'])
        if not streams:return data
        mask=streams[0]
        if len(mask.shape)==5 and tuple(mask.shape[-2:])!=tuple(new_hw):
            from .latent_utils import spatial_interpolate_video_latent
            mask=spatial_interpolate_video_latent(mask,*new_hw,mode='nearest')
        from .continuity import repack_av_latent
        return {**data,'noise_mask':repack_av_latent(mask,streams[1])['samples'] if len(streams)>1 else mask}
    if upscale_method != 'latent' and refine_mode in ('upscale','latent_upscale'):
        if video_vae is None: raise ValueError('Pixel upscale before refinement requires Video VAE.')
        from .executor import decode_video_latent
        try:
            from ..nodes.node_pixel_upscale import MiniMaxH3PixelUpscale
        except ImportError:
            from nodes.node_pixel_upscale import MiniMaxH3PixelUpscale
        pixels=decode_video_latent(video_vae,video)
        pixels=MiniMaxH3PixelUpscale().upscale(pixels,provider=upscale_method,width=target_width,height=target_height,upscale_model=upscale_model,resize_method=resize_method)[0]
        old_hw=video.shape[-2:]
        video=video_vae.encode(pixels)
        from .advanced_sampling import resize_conditioning
        positive=resize_conditioning(positive,old_hw,video.shape[-2:])
        negative=resize_conditioning(negative,old_hw,video.shape[-2:])
        import comfy.nested_tensor
        latent_dict={**latent_dict,'samples':comfy.nested_tensor.NestedTensor((video,audio))}
        latent_dict=resized_masks(latent_dict,video.shape[-2:])
        target_width,target_height=int(pixels.shape[2]),int(pixels.shape[1])
        latent_upscale_model=None
        del pixels
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
                seed=pass_seed(index), vae=video_vae, start_image=first_frame,
                director_guide={"first_frame": first_frame, "last_frame": last_frame},
                negative=negative, cfg=cfg, sampler_name=sampler_name, scheduler=scheduler,
                memory_budget_mb=memory_budget_mb, spatial_tiling=enable_tiling,
                temporal_chunking=enable_chunking, target_width=target_w, target_height=target_h,
                external_sigmas=sigmas, upscale_precision=upscale_precision,
                continuity_context=continuity, continuity_soft_refine=continuity is not None,
                spike_guard=spike_guard,guard_sensitivity=guard_sensitivity,guard_strength=guard_strength,guard_mode=guard_mode,memory_planning=memory_planning,memory_reserve_pct=memory_reserve_pct)
            result["_mmx_refine_report"] = report
            if pass_callback: pass_callback(index+1,result)
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
            if spike_guard:
                from .vendor.dasiwa.h3_spike_guard import spike_guard as correct_spikes
                source_video=extract_streams_from_av_latent(latent_dict)[0]
                video,report=correct_spikes(source_video,video,sensitivity=guard_sensitivity,strength=guard_strength,mode=guard_mode)
                latent_dict={**latent_dict,'_mmx_refine_report':report}
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
        latent_dict=resized_masks(latent_dict,video.shape[-2:])

    if refine_mode == "latent_upscale":
        # No sampling pass requested; return upscaled latents directly
        if pass_callback: pass_callback(1,latent_dict)
        return latent_dict

    for pass_index in range(int(passes)):
        log.info("Refine %s pass %d/%d", refine_mode, pass_index + 1, passes)
        if enable_tiling:
            from .advanced_sampling import sample_stage
            latent_dict = sample_stage(active_model, latent_dict, steps, cfg,
                sampler_name, scheduler, positive, negative, pass_seed(pass_index),
                denoise, sigmas=sigmas, tile_count=tile_count, tile_overlap=tile_overlap)
        else:
            latent_dict = sample_latent(active_model, latent_dict, steps, cfg,
                sampler_name, scheduler, positive, negative, pass_seed(pass_index),
                denoise=denoise, sigmas=sigmas)
        if pass_callback: pass_callback(pass_index+1,latent_dict)
    return latent_dict
