"""Manual look adjustments for continuity frames.

One small, fixed grade shared by the Python pipeline and the browser preview
(web/js/minimax_director.js ``applyLookPixels``): the browser shows exactly what
generation will receive. Images are float RGB in 0..1, channels last.
"""

from __future__ import annotations

import math

NEUTRAL = {"exposure": 0.0, "contrast": 1.0, "black": 0.0, "saturation": 1.0, "temperature": 0.0, "tint": 0.0}
RANGES = {"exposure": (-2.0, 2.0), "contrast": (0.5, 1.5), "black": (-0.1, 0.1),
          "saturation": (0.0, 2.0), "temperature": (-1.0, 1.0), "tint": (-1.0, 1.0)}


def clean_look(look):
    """Validated look values, or None when the look is absent or neutral."""
    if not look or not isinstance(look, dict):
        return None
    values = {}
    for key, neutral in NEUTRAL.items():
        value = float(look.get(key, neutral))
        low, high = RANGES[key]
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"Look {key} must be between {low} and {high}.")
        values[key] = value
    if all(abs(values[key] - NEUTRAL[key]) < 1e-6 for key in NEUTRAL):
        return None
    return values


def apply_look(images, look):
    """Grade ``images`` [..., 3]; returns the input unchanged for a neutral look."""
    values = clean_look(look)
    if values is None or images is None:
        return images
    x = images.float() * (2.0 ** values["exposure"])
    t, g = values["temperature"], values["tint"]
    gains = x.new_tensor([(1 + 0.1 * t) * (1 - 0.05 * g), 1 + 0.1 * g, (1 - 0.1 * t) * (1 - 0.05 * g)])
    x = x * gains
    x = (x - 0.5) * values["contrast"] + 0.5
    lift = values["black"]
    x = lift + x * (1 - lift)
    luma = (x * x.new_tensor([0.299, 0.587, 0.114])).sum(dim=-1, keepdim=True)
    x = luma + (x - luma) * values["saturation"]
    return x.clamp(0, 1).to(images.dtype)


# "Hold look to chain start": a per-channel gain on delivered frames that pulls
# a continued clip's colour balance back to the chain's first clip. Brightness
# is left alone (the prompt may brighten or darken the end on purpose), so the
# gain is normalised to keep luma. It ramps from the previous clip's end gain
# (seamless join) to this clip's own target.
HOLD_MIN, HOLD_MAX = 0.75, 1.33


def mean_rgb(frames, count=24):
    tail = frames[-min(int(count), int(frames.shape[0])):][::3].float()
    return [float(v) for v in tail.mean(dim=(0, 1, 2))]


def hold_target(anchor_rgb, raw_end_rgb):
    """Per-channel gain matching the anchor's colour balance at unchanged brightness."""
    gains = [a / max(r, 1e-4) for a, r in zip(anchor_rgb, raw_end_rgb)]
    luma = sum(w * g * r for w, g, r in zip((0.299, 0.587, 0.114), gains, raw_end_rgb))
    base = sum(w * r for w, r in zip((0.299, 0.587, 0.114), raw_end_rgb))
    scale = base / max(luma, 1e-6)
    return [min(HOLD_MAX, max(HOLD_MIN, g * scale)) for g in gains]


def _curve(hold, total, start, stop, like):
    import torch
    a = torch.tensor(hold["start"], dtype=torch.float32)
    b = torch.tensor(hold["end"], dtype=torch.float32)
    k = torch.arange(start, stop, dtype=torch.float32) / max(1, int(total) - 1)
    return (a + (b - a) * k.view(-1, 1)).view(-1, 1, 1, 3).to(like.device)


def frame_stats(frames, count=24, from_end=False):
    """Mean RGB (0..1) and luma spread of up to ``count`` frames, sampled cheaply."""
    total = int(frames.shape[0])
    n = min(int(count), total)
    part = frames[total - n:] if from_end else frames[:n]
    x = part[::3, ::4, ::4].float()
    if x.numel() and float(x.max()) > 2:
        x = x / 255
    luma = 0.299 * x[..., 0] + 0.587 * x[..., 1] + 0.114 * x[..., 2]
    return {"rgb": [float(v) for v in x.mean(dim=(0, 1, 2))], "std": float(luma.std())}


def apply_hold(frames, hold, directory=None):
    """Return frames with the hold gain applied (bounded windows when ``directory``)."""
    total = int(frames.shape[0])
    if directory is None:
        return (frames.float() * _curve(hold, total, 0, total, frames)).clamp(0, 1).to(frames.dtype)
    from .output_retention import process_video_frames
    offset = [0]
    def grade(window):
        n = int(window.shape[0])
        out = (window.float() * _curve(hold, total, offset[0], offset[0] + n, window)).clamp(0, 1).to(window.dtype)
        offset[0] += n
        return out
    return process_video_frames(frames, directory, grade)


def undo_hold(tail, hold, total):
    """Invert the hold gain on the last ``tail`` frames of a clip of ``total`` frames."""
    if not hold:
        return tail
    n = int(tail.shape[0])
    return (tail.float() / _curve(hold, total, total - n, total, tail)).clamp(0, 1).to(tail.dtype)
