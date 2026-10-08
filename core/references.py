"""File references share the graph reference pool and native label planner."""
from __future__ import annotations
import math
from .media_io import load_image, load_video, load_audio, scale_tensor_image

ROLES = ("subject", "place", "style", "keyframe", "pose", "custom")


def edit_images(images, edits=None, crop=None):
    if not edits and not crop:
        return images
    if crop:
        x, y, width, height = [float(crop.get(key, default)) for key, default in [("x", 0), ("y", 0), ("width", 1), ("height", 1)]]
        if not all(math.isfinite(n) for n in (x, y, width, height)) or min(x, y) < 0 or min(width, height) <= 0 or x + width > 1.000001 or y + height > 1.000001:
            raise ValueError("Reference crop must lie within the normalized image bounds.")
        h, w = images.shape[1:3]
        images = images[:, int(y*h):max(int(y*h)+1, round((y+height)*h)), int(x*w):max(int(x*w)+1, round((x+width)*w))]
    edits = edits or {}
    exposure = float(edits.get("exposure", 0))
    contrast = float(edits.get("contrast", 1))
    saturation = float(edits.get("saturation", 1))
    if not all(math.isfinite(n) for n in (exposure, contrast, saturation)) or not -10 <= exposure <= 10 or not 0 <= min(contrast, saturation) or max(contrast, saturation) > 4:
        raise ValueError("Invalid image exposure/contrast/saturation.")
    images = images * 2**exposure
    images = (images - .5) * contrast + .5
    gray = images[..., :3].mean(dim=-1, keepdim=True)
    images = gray + (images - gray) * saturation
    return images.clamp(0, 1)


def load_reference(row, root, width=1344, height=768):
    if row.get("role", "subject") not in ROLES:
        raise ValueError(f"Unknown reference role: {row.get('role')}")
    kind = row.get("type", "image")
    path = row.get("filename")
    if not path:
        raise ValueError("Uploaded references need a filename.")
    start = float(row.get("start", 0))
    end = row.get("end")
    end = float(end) if end is not None else None
    if not math.isfinite(start) or end is not None and not math.isfinite(end):
        raise ValueError("Reference trim times must be finite.")
    scaling = row.get("scaling", "Auto")
    rows = []
    if kind == "image":
        pixels = load_image(path, root, scaling_mode="Off")
        data = scale_tensor_image(edit_images(pixels, row.get("edits"), row.get("crop")), scaling, width, height)
        rows.append({**row, "data": data})
    elif kind == "video":
        mode = row.get("media_mode", "video")
        if mode not in ("video", "audio", "both"):
            raise ValueError("Video reference mode must be video, audio or both.")
        if mode in ("video", "both"):
            pixels = load_video(path, root, trim_start=start, trim_end=end)
            rows.append({**row, "data": scale_tensor_image(edit_images(pixels, row.get("edits"), row.get("crop")), scaling, width, height)})
        if mode in ("audio", "both"):
            rows.append({**row, "id": row["id"] + "_audio", "type": "audio", "data": load_audio(path, root, trim_start=start, trim_end=end), **({"paired_video_id": row["id"]} if mode == "both" else {})})
    elif kind == "audio":
        rows.append({**row, "data": load_audio(path, root, trim_start=start, trim_end=end)})
    else:
        raise ValueError(f"Unsupported uploaded reference type: {kind}")
    return rows


def waveform(audio, points=256):
    data = audio["waveform"].detach().float().cpu().abs().amax(dim=(0, 1))
    points = max(8, min(int(points), 2048))
    if data.numel() == 0:
        return []
    points = min(points, len(data))
    return [float(data[round(i*len(data)/points):max(round(i*len(data)/points)+1, round((i+1)*len(data)/points))].max()) for i in range(points)]
