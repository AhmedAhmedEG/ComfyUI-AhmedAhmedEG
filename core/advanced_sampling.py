"""Shared adapters for the selected native sampler algorithms."""
from __future__ import annotations


def _install_scoped_remask(model, latent, sigmas):
    from .vendor.aimixer.director.h3_latent_continue import install_continue_prefix_remask
    from .run_resources import current_resources
    patched = install_continue_prefix_remask(model, latent, sigmas)
    owner = current_resources()
    if owner is not None and patched is not model:
        owner.track_transient(patched)
    return patched


def sample_stage(model, latent, steps, cfg, sampler, scheduler, positive, negative,
                 seed, denoise=1., sigmas=None, tile_count=1, tile_overlap=128):
    from .vendor.aimixer.director.core_sampling import sample_single_stage
    return sample_single_stage(model=model, positive=positive, negative=negative,
        latent=latent, seed=seed, cfg=cfg, steps=steps, sampler_name=sampler,
        scheduler=scheduler, denoise=denoise, sigmas=sigmas, apply_shift=False,
        enable_tiling=tile_count > 1, tile_count=tile_count, tile_overlap=tile_overlap,
        after_shift=_install_scoped_remask if latent.get("_director_continue_prefix_steps") else None)


def sample_selflift(model, positive, negative, latent, seed, steps, cfg, sampler,
                    scheduler, settings, video_vae, width, height,
                    shift_video=12., shift_audio=3., sigmas=None, carry=None,
                    pin_frames=0):
    from .vendor.aimixer.director.selflift.pack import normalize_selflift_pack
    from .vendor.aimixer.director.selflift.sample import sample_selflift_stage
    from .vendor.aimixer.director.core_sampling import ShiftedModelCache
    from .run_resources import current_resources
    pack = normalize_selflift_pack(settings)
    if pack is None:
        raise ValueError("SelfLift settings must be enabled.")
    return sample_selflift_stage(model=model, positive=positive, negative=negative,
        latent=latent, seed=seed, steps=steps, cfg=cfg, sampler_name=sampler,
        scheduler=scheduler, pack=pack, vae=video_vae, canvas_width=width,
        canvas_height=height, shift_video=shift_video, shift_audio=shift_audio,
        sigmas=sigmas, shift_cache=current_resources() or ShiftedModelCache(), prev_low_carry=carry,
        pin_frames=pin_frames, after_shift=_install_scoped_remask if latent.get("_director_continue_prefix_steps") else None)


def resize_conditioning(positive, old_hw, new_hw):
    from .vendor.aimixer.director.selflift.cond import resize_positive_spatial
    return resize_positive_spatial(positive, *old_hw, *new_hw, "bilinear")
