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
# Optional calibrated tone curve, applied after the sliders: one lookup table
# per channel, CURVE_POINTS outputs for evenly spaced inputs 0..1. Auto
# calibrate fits it so the darks, mids and whites each match, not just averages.
CURVE_POINTS = 33
# Tone measurement points (fractions of pixels) for calibration.
TONE_QUANTILES = (0.005, 0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98, 0.995)


def clean_curve(curve):
    """Validated monotone per-channel lookup tables, or None for an identity/absent curve."""
    if curve is None:
        return None
    if not isinstance(curve, (list, tuple)) or len(curve) != 3:
        raise ValueError("Look curve must have three channels.")
    out = []
    for channel in curve:
        if not isinstance(channel, (list, tuple)) or len(channel) != CURVE_POINTS:
            raise ValueError(f"Each look curve channel must have {CURVE_POINTS} points.")
        values, top = [], 0.0
        for value in channel:
            value = float(value)
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError("Look curve values must be between 0 and 1.")
            top = max(top, value)
            values.append(top)
        out.append(values)
    step = 1.0 / (CURVE_POINTS - 1)
    if all(abs(v - i * step) < 1e-4 for channel in out for i, v in enumerate(channel)):
        return None
    return out


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
    curve = clean_curve(look.get("curve"))
    if curve is None and all(abs(values[key] - NEUTRAL[key]) < 1e-6 for key in NEUTRAL):
        return None
    if curve is not None:
        values["curve"] = curve
    return values


def apply_curve(x, curve):
    """Per-channel piecewise-linear lookup on float RGB 0..1 [..., 3]."""
    import torch
    lut = torch.tensor(curve, dtype=torch.float32, device=x.device)  # [3, P]
    pos = x.clamp(0, 1) * (CURVE_POINTS - 1)
    lo = pos.floor().clamp(0, CURVE_POINTS - 2)
    frac = pos - lo
    lo = lo.long()
    out = torch.empty_like(x)
    for c in range(3):
        table = lut[c]
        a = table[lo[..., c]]
        b = table[lo[..., c] + 1]
        out[..., c] = a + (b - a) * frac[..., c]
    return out


def tone_quantiles(frames, count=24, from_end=False):
    """Per-channel values (0..1) at TONE_QUANTILES over up to ``count`` frames."""
    import torch
    total = int(frames.shape[0])
    n = min(int(count), total)
    part = frames[total - n:] if from_end else frames[:n]
    x = part[::3, ::4, ::4].float()
    if x.numel() and float(x.max()) > 2:
        x = x / 255
    x = x.reshape(-1, 3)
    if x.shape[0] > 2_000_000:
        x = x[:: x.shape[0] // 2_000_000 + 1]
    q = torch.tensor(TONE_QUANTILES, dtype=torch.float32)
    return [[float(v) for v in torch.quantile(x[:, c], q)] for c in range(3)]


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
    x = x.clamp(0, 1)
    if values.get("curve"):
        x = apply_curve(x, values["curve"])
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


def undo_hold_at(frames, hold, total, start):
    """Invert the hold gain on ``frames`` that begin at frame ``start`` of a clip of ``total`` frames."""
    if not hold:
        return frames
    n = int(frames.shape[0])
    x = frames.float()
    scale = 255.0 if x.numel() and float(x.max()) > 2 else 1.0
    out = (x / scale / _curve(hold, total, int(start), int(start) + n, frames)).clamp(0, 1)
    return out


def undo_hold(tail, hold, total):
    """Invert the hold gain on the last ``tail`` frames of a clip of ``total`` frames."""
    if not hold:
        return tail
    n = int(tail.shape[0])
    return (tail.float() / _curve(hold, total, total - n, total, tail)).clamp(0, 1).to(tail.dtype)


def fit_tone_lut(start_tones, target_tones, limit=0.25):
    """Per-channel lookup tables mapping ``start_tones`` onto ``target_tones``
    (histogram matching at TONE_QUANTILES); mirrors fitToneCurve in
    web/js/minimax_look.js. None when the two already match."""
    tables = []
    for c in range(3):
        xs, ys = [], []
        for x, y in zip(start_tones[c], target_tones[c]):
            if xs and x <= xs[-1] + 1e-4:
                ys[-1] = max(ys[-1], y)
                continue
            xs.append(float(x)); ys.append(float(y))
        def correct(x):
            if not xs:
                return x
            if x <= xs[0]:
                return ys[0] + (x - xs[0])
            if x >= xs[-1]:
                return ys[-1] + (x - xs[-1])
            k = 1
            while xs[k] < x:
                k += 1
            return ys[k - 1] + (ys[k] - ys[k - 1]) * (x - xs[k - 1]) / (xs[k] - xs[k - 1])
        top, table = 0.0, []
        for i in range(CURVE_POINTS):
            x = i / (CURVE_POINTS - 1)
            y = min(1.0, max(0.0, max(x - limit, min(x + limit, correct(x)))))
            top = max(top, y)
            table.append(round(top, 4))
        tables.append(table)
    return clean_curve(tables)


# "Match the join after decoding": the new clip's opening is tone-matched to
# the previous clip's end (darks, mids and whites per channel), at full
# strength on the first new frame and fading out over JOIN_MATCH_FRAMES so the
# model's own look takes over smoothly. Frames before ``start`` (reused
# context, trimmed on delivery) get the full correction.
JOIN_MATCH_FRAMES = 24


def match_join(frames, target, start, ramp=JOIN_MATCH_FRAMES, count=24):
    """Tone-match the opening of ``frames`` (new content from ``start``) to the
    end of ``target``. Edits ``frames`` in place; returns (frames, info) where
    info holds the opening's measurements before matching (for calibration)."""
    import torch
    total = int(frames.shape[0])
    start = max(0, min(int(start), total - 1))
    first = frames[start:start + int(count)]
    info = {"first": frame_stats(first), "first_tones": tone_quantiles(first), "frames": int(ramp), "amount": 0.0}
    lut = fit_tone_lut(info["first_tones"], tone_quantiles(target, from_end=True))
    if lut is None:
        return frames, info
    step = 1.0 / (CURVE_POINTS - 1)
    info["amount"] = round(max(abs(v - i * step) for table in lut for i, v in enumerate(table)), 4)
    n = min(total, start + int(ramp))
    head = frames[:n].float()
    scale = 255.0 if head.numel() and float(head.max()) > 2 else 1.0
    head = head / scale
    k = ((torch.arange(n, dtype=torch.float32) - start) / max(1, int(ramp))).clamp(0, 1)
    weight = (1 - k * k * (3 - 2 * k)).view(-1, 1, 1, 1).to(head.device)
    out = head + (apply_curve(head, lut) - head) * weight
    frames[:n] = (out.clamp(0, 1) * scale).to(frames.dtype)
    return frames, info
