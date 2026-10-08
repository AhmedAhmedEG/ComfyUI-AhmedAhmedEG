"""Non-destructive playback, watermark and loop processing for decoded media."""
import math
import torch
import torch.nn.functional as F
from .audio_post import fit_audio_duration


def playback(frames, audio, source_fps, target_fps, policy="resample"):
    if not all(math.isfinite(float(v)) and v > 0 for v in (source_fps, target_fps)):
        raise ValueError("Playback rates must be finite and positive.")
    if policy == "resample":
        count = max(1, round(frames.shape[0] * target_fps / source_fps))
        indices = torch.arange(count, device=frames.device).mul(source_fps/target_fps).long().clamp(max=frames.shape[0]-1)
        frames = frames[indices]
    elif policy == "retime":
        # Retiming changes speed and pitch; resample preserves wall-clock time.
        if audio is not None:
            waveform = audio["waveform"]
            size = max(1, round(waveform.shape[-1] * source_fps/target_fps))
            audio = {**audio, "waveform": F.interpolate(waveform.float(), size=size, mode="linear", align_corners=False)}
    else:
        raise ValueError("Playback policy must be resample or retime.")
    return frames, fit_audio_duration(audio, frames.shape[0], target_fps) if audio else audio


def watermark(frames, text="", logo=None, opacity=.5, corner="bottom_right", margin=16, font_size=24):
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np
    if not math.isfinite(opacity) or not 0 <= opacity <= 1:
        raise ValueError("Watermark opacity must be in [0,1].")
    if corner not in ("top_left", "top_right", "bottom_left", "bottom_right"):
        raise ValueError("Unknown watermark corner.")
    if logo is not None:
        pixels = logo[0] if logo.ndim == 4 else logo
        patch = pixels[..., :3].to(device=frames.device, dtype=frames.dtype)
        alpha = pixels[..., 3:4] if pixels.shape[-1] > 3 else torch.ones_like(pixels[..., :1])
        alpha = alpha.to(device=frames.device, dtype=frames.dtype) * opacity
    elif text:
        try: font = ImageFont.truetype("arial.ttf", font_size)
        except OSError: font = ImageFont.load_default()
        bounds = font.getbbox(text)
        image = Image.new("RGBA", (max(1, bounds[2]-bounds[0]+8), max(1, bounds[3]-bounds[1]+8)))
        ImageDraw.Draw(image).text((4-bounds[0], 4-bounds[1]), text, font=font, fill=(255,255,255,255), stroke_width=1, stroke_fill=(0,0,0,255))
        pixels = torch.from_numpy(np.asarray(image).copy()).to(device=frames.device, dtype=frames.dtype)/255
        patch, alpha = pixels[..., :3], pixels[..., 3:4]*opacity
    else:
        return frames
    h, w = frames.shape[1:3]
    ph, pw = patch.shape[:2]
    if ph > h or pw > w:
        scale = min(h/ph, w/pw)
        size = (max(1, int(ph*scale)), max(1, int(pw*scale)))
        patch = F.interpolate(patch.permute(2,0,1)[None], size=size, mode="bilinear", align_corners=False)[0].permute(1,2,0)
        alpha = F.interpolate(alpha.permute(2,0,1)[None], size=size, mode="bilinear", align_corners=False)[0].permute(1,2,0)
        ph, pw = size
    x = max(0, min(w-pw, margin if corner.endswith("left") else w-pw-margin))
    y = max(0, min(h-ph, margin if corner.startswith("top") else h-ph-margin))
    result = frames.clone()
    result[:, y:y+ph, x:x+pw, :3] = result[:, y:y+ph, x:x+pw, :3]*(1-alpha)+patch*alpha
    return result


def seamless_loop(frames, audio, fps, overlap_frames):
    n = int(overlap_frames)
    if n < 1 or n*2 >= frames.shape[0]:
        raise ValueError("Loop overlap must be positive and less than half the video length.")
    weights = torch.linspace(0, 1, n, device=frames.device, dtype=frames.dtype).reshape(n,1,1,1)
    blended = frames[-n:]*(1-weights) + frames[:n]*weights
    result = torch.cat([frames[n:-n], blended], dim=0)
    if audio:
        audio = fit_audio_duration(audio, frames.shape[0], fps)
        waveform = audio["waveform"]
        samples = max(1, round(n/fps*audio["sample_rate"]))
        ramp = torch.linspace(0, 1, samples, device=waveform.device, dtype=waveform.dtype)
        audio = {**audio, "waveform": torch.cat([waveform[..., samples:-samples], waveform[..., -samples:]*(1-ramp)+waveform[..., :samples]*ramp], dim=-1)}
        audio = fit_audio_duration(audio, result.shape[0], fps)
    return result, audio
