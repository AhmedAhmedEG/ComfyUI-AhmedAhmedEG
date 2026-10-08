"""LATENT dictionary adapter for ComfyUI's tensor-level sampling API."""

from __future__ import annotations


def sample_latent(model, latent, steps, cfg, sampler_name, scheduler,
                  positive, negative, seed, denoise=1.0, *, sigmas=None,
                  disable_noise=False, start_step=None, last_step=None,
                  force_full_denoise=False):
    import comfy.sample

    if steps < 1:
        raise ValueError("Sampling steps must be positive.")
    if sigmas is not None:
        values = sigmas.tolist()
        import math
        if (len(values) < 2 or any(not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in values)
                or any(a < b for a, b in zip(values, values[1:]))):
            raise ValueError("SIGMAS must be a finite, non-negative, decreasing one-dimensional schedule.")

    samples = latent["samples"]
    samples = comfy.sample.fix_empty_latent_channels(
        model, samples, latent.get("downscale_ratio_spacial"),
        latent.get("downscale_ratio_temporal"))
    noise = (comfy.sample.prepare_empty_noise(samples) if disable_noise else
             comfy.sample.prepare_noise(samples, seed, latent.get("batch_index")))
    try:
        import latent_preview
        callback = latent_preview.prepare_callback(model, steps)
    except ImportError:
        callback = None
    result = comfy.sample.sample(
        model, noise, steps, cfg, sampler_name, scheduler, positive, negative,
        samples, denoise=denoise, disable_noise=disable_noise,
        start_step=start_step, last_step=last_step,
        force_full_denoise=force_full_denoise, noise_mask=latent.get("noise_mask"),
        sigmas=sigmas, callback=callback, seed=seed)
    output = dict(latent)
    output.pop("downscale_ratio_spacial", None)
    output.pop("downscale_ratio_temporal", None)
    output["samples"] = result
    return output


def native_outputs(result):
    """Unwrap both modern io.NodeOutput and legacy tuple node results."""
    return result.result if hasattr(result, "result") else result
