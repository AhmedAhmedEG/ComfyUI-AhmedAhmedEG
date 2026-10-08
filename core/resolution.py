"""One working-canvas planner for generated shots and imported video."""
import math
from .config import calculate_dimensions_for_aspect_and_mp, snap_to_multiple


def timeline_media_size(timeline):
    from .media_io import resolve_input_path
    import folder_paths
    root = folder_paths.get_input_directory()
    source = timeline.get("source")
    rows = ([{"filename": source}] if isinstance(source, str) else [source] if source else [])
    rows += [row for row in timeline.get("references", []) if row.get("type") in ("image", "video")]
    for row in rows:
        if not row.get("filename"): continue
        path = resolve_input_path(row["filename"], root)
        from PIL import Image
        try:
            with Image.open(path) as image: return image.size
        except (OSError, ValueError):
            import av
            with av.open(path) as container:
                if container.streams.video:
                    stream = container.streams.video[0]
                    return stream.width, stream.height
    return None


def plan_canvas(settings, source_size=None):
    policy = settings.get("mode", "manual")
    if policy == "original":
        if source_size is None: raise ValueError("Original canvas needs a source image/video size.")
        width, height = [snap_to_multiple(value, 32) for value in source_size]
    elif policy == "auto":
        aspect = settings.get("aspect", "16:9")
        if aspect == "auto":
            if source_size is None: raise ValueError("Auto aspect needs a source image/video size.")
            ratio = source_size[0]/source_size[1]
            mp = float(settings.get("megapixels", 1.))
            if not math.isfinite(mp) or mp <= 0: raise ValueError("Megapixels must be finite and positive.")
            height = snap_to_multiple(math.sqrt(mp*1e6/ratio), 32)
            width = snap_to_multiple(height*ratio, 32)
        else:
            width, height = calculate_dimensions_for_aspect_and_mp(aspect, float(settings.get("megapixels", 1.)))
    elif policy == "manual":
        width, height = int(settings.get("width", 1344)), int(settings.get("height", 768))
    else:
        raise ValueError("Canvas mode must be manual, original or auto.")
    if min(width, height) < 32 or max(width, height) > 16384 or width % 32 or height % 32:
        raise ValueError("Working canvas must be divisible by 32 and within 32–16384 pixels.")
    return width, height
