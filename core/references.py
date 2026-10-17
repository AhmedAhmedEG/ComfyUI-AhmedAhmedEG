"""File references share the graph reference pool and native label planner."""
from __future__ import annotations
import math
from .media_io import load_image, load_video, load_audio, scale_tensor_image

ROLES = ("subject", "place", "style", "keyframe", "pose", "custom")


def resize_reference(images, settings, kind):
    """One pool-owned resize path for graph-connected and file-backed assets."""
    scaling = settings.get('scaling', 'Megapixels' if kind == 'video' else 'Off')
    if scaling == 'Megapixels':
        mp = float(settings.get('megapixels', .5))
        h, w = images.shape[1:3]
        if kind == 'video':
            from .source_media import video_input_dimensions
            width, height = video_input_dimensions(w, h, {'mode': 'megapixels', 'megapixels': mp})
        else:
            if not math.isfinite(mp) or not .001024 <= mp <= 16:
                raise ValueError('Reference image budget must be between 0.001024 and 16 megapixels.')
            scale = min(1., math.sqrt(mp * 1_000_000 / (w * h)))
            width, height = max(32, math.floor(w * scale / 32) * 32), max(32, math.floor(h * scale / 32) * 32)
        return scale_tensor_image(images, 'Target', width, height)
    return scale_tensor_image(images, scaling, int(settings.get('width', 1344)), int(settings.get('height', 768)))


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
    if edits.get('model')=='css':
        # Tritant's CSS/FFmpeg saturate -> contrast -> brightness order.
        gray=images[...,0:1]*.213+images[...,1:2]*.715+images[...,2:3]*.072
        images=gray+(images-gray)*saturation
        return ((images-.5)*contrast+.5).mul(2**exposure).clamp(0,1)
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
    resize_settings = {'width': width, 'height': height, **row}
    rows = []
    if kind == "image":
        pixels = load_image(path, root, scaling_mode="Off")
        data = resize_reference(edit_images(pixels, row.get("edits"), row.get("crop")), resize_settings, 'image')
        rows.append({**row, "data": data})
    elif kind == "video":
        mode = row.get("media_mode", "video")
        if mode not in ("video", "audio", "both", "frame"):
            raise ValueError("Video reference mode must be video, audio or both.")
        if mode in ("video", "both", "frame"):
            pixels = load_video(path, root, trim_start=start, trim_end=end)
            if mode=="frame":
                time=float(row.get("frame_time",0));index=round(time*24)
                if not math.isfinite(time) or index<0 or index>=pixels.shape[0]:raise ValueError("Frame pick is outside trimmed video.")
                pixels=pixels[index:index+1]
            rows.append({**row, "type":"image" if mode=="frame" else "video", "data": resize_reference(edit_images(pixels, row.get("edits"), row.get("crop")), resize_settings, 'video')})
        if mode in ("audio", "both"):
            rows.append({**row, "id": row["id"] + "_audio" if mode=="both" else row["id"], "type": "audio", "data": load_audio(path, root, trim_start=start, trim_end=end), **({"paired_video_id": row["id"]} if mode == "both" else {})})
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
