"""3D latent lift + optional paper rho pixel-anchor mix."""


from __future__ import annotations


import logging


import torch


import torch.nn.functional as F


from ..h3_latent_upscale import upscale_h3_video_latent


from .cond import interpolate_video_5d


from .grid import pixel_to_latent_hw


log = logging.getLogger("ComfyUI-MiniMaxH3-Director.selflift.lift")


def _as_video_dict(video: torch.Tensor) -> dict:
    return {"samples": video}


def lift_video_tensor(
    video: torch.Tensor,
    *,
    src_width: int,
    src_height: int,
    dst_width: int,
    dst_height: int,
    model_name: str = "",
    model=None,
    enable_chunking: bool = False,
    fallback: str = "bilinear",
    prefix_steps: int = 0,
) -> torch.Tensor:
    """Spatially lift a BCTHW / CTHW video latent to the target canvas.

    ``prefix_steps`` splits the 3D net at the continue boundary so the new
    suffix sees the real low-res prefix as left context.
    """
    dst_lat_h, dst_lat_w = pixel_to_latent_hw(dst_width, dst_height)
    work = video
    squeezed = False
    if work.ndim == 4:
        work = work.unsqueeze(0)
        squeezed = True
    if int(work.shape[-2]) == int(dst_lat_h) and int(work.shape[-1]) == int(dst_lat_w):
        return video
    try:
        packed = upscale_h3_video_latent(
            _as_video_dict(work),
            target_width=int(dst_width),
            target_height=int(dst_height),
            source_width=int(src_width),
            source_height=int(src_height),
            model_name=model_name,
            model=model,
            enable_latent_chunking=bool(enable_chunking),
            temporal_split=int(prefix_steps or 0),
        )
        out = packed["samples"]
    except Exception as exc:
        raise RuntimeError("SelfLift learned lift failed; check the selected H3 checkpoint.") from exc
    if squeezed and torch.is_tensor(out) and out.ndim == 5 and out.shape[0] == 1:
        out = out.squeeze(0)
    return out


def _highfreq_weights(z_3d: torch.Tensor, z_pix: torch.Tensor, w_min: float, w_max: float) -> torch.Tensor:
    """Heavier blend on high-frequency residual (paper artifact-aware mix)."""
    diff = (z_pix.float() - z_3d.float()).abs().mean(dim=1, keepdim=True)
    kernel = z_3d.new_tensor(
        [[[[0.0, -1.0, 0.0], [-1.0, 4.0, -1.0], [0.0, -1.0, 0.0]]]]
    )
    # Per-frame 2D laplacian on the residual magnitude.
    b, _, t, h, w = diff.shape
    flat = diff.permute(0, 2, 1, 3, 4).reshape(b * t, 1, h, w)
    lap = F.conv2d(flat, kernel.to(device=flat.device, dtype=flat.dtype), padding=1).abs()
    lap = lap.reshape(b, t, 1, h, w).permute(0, 2, 1, 3, 4)
    flat_n = lap.reshape(b, -1)
    lo = flat_n.min(dim=1, keepdim=True).values
    hi = flat_n.max(dim=1, keepdim=True).values
    norm = (flat_n - lo) / (hi - lo).clamp_min(1e-6)
    norm = norm.reshape_as(lap)
    w = float(w_min) + (float(w_max) - float(w_min)) * norm
    return w.clamp(0.0, 1.0).to(dtype=z_3d.dtype)


def mix_rho(z_3d: torch.Tensor, z_pix: torch.Tensor, rho: float, w_min: float, w_max: float) -> torch.Tensor:
    if float(rho) <= 1e-8 or z_pix is None:
        return z_3d
    squeezed = False
    a, b = z_3d, z_pix
    if a.ndim == 4:
        a = a.unsqueeze(0)
        squeezed = True
    if b.ndim == 4:
        b = b.unsqueeze(0)
    if tuple(a.shape[-2:]) != tuple(b.shape[-2:]):
        b = interpolate_video_5d(b, int(a.shape[-2]), int(a.shape[-1]), "bilinear")
    w = _highfreq_weights(a, b, w_min, w_max)
    out = a + float(rho) * w * (b - a)
    if squeezed:
        out = out.squeeze(0)
    return out.contiguous()


def pixel_anchor_latent(
    x0_low: torch.Tensor,
    *,
    vae,
    src_width: int,
    src_height: int,
    dst_width: int,
    dst_height: int,
) -> torch.Tensor | None:
    """Decode low x0 → lanczos pixels → encode at the target canvas. Optional rho mix."""
    if vae is None:
        return None
    video = x0_low
    if video.ndim == 4:
        video = video.unsqueeze(0)
    try:
        # MiniMax video VAE decode: [B,C,T,H,W] → frames. Prefer process_output path.
        decoded = vae.decode(video)
        if isinstance(decoded, dict):
            decoded = decoded.get("samples") or decoded.get("image") or decoded
        if not torch.is_tensor(decoded):
            return None
        frames = decoded
        if frames.ndim == 5:
            # B C T H W or B T H W C
            if frames.shape[1] in (3, 4) and frames.shape[-1] not in (3, 4):
                frames = frames.permute(0, 2, 3, 4, 1)
            frames = frames.reshape(-1, frames.shape[-3], frames.shape[-2], frames.shape[-1])
        if frames.ndim != 4:
            return None
        from comfy.utils import common_upscale

        pix = frames.movedim(-1, 1)
        pix = common_upscale(pix, int(dst_width), int(dst_height), "lanczos", "disabled")
        pix = pix.movedim(1, -1).clamp(0.0, 1.0)
        encoded = vae.encode(pix)
        if isinstance(encoded, dict):
            encoded = encoded.get("samples") or encoded
        if not torch.is_tensor(encoded):
            return None
        # Reassemble T from the low-res time axis.
        t = int(video.shape[2])
        if encoded.ndim == 4:
            c, h, w = encoded.shape[-3], encoded.shape[-2], encoded.shape[-1]
            encoded = encoded.reshape(-1, t, c, h, w).permute(0, 2, 1, 3, 4)
        return encoded.to(dtype=x0_low.dtype)
    except Exception as exc:
        log.warning("SelfLift pixel-anchor encode skipped (%s).", exc)
        return None
