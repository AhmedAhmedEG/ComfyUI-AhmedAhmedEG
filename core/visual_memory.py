"""Clip memory: show H3 moments from earlier clips as reference videos.

A clip's ``memory`` list names earlier clips, optionally a time range inside
each, plus a short note of what the moment shows. At generation time each
entry becomes one reference video cut from that clip's saved frames, and a
visible note is added to the prompt so H3 knows those videos are earlier
moments of the same film. The editor shows the exact same note text.
"""
from __future__ import annotations

import math
import re

from .config import FPS, MAX_REF_VIDEOS, align_frame_count

MEMORY_LIMIT = MAX_REF_VIDEOS
MIN_WINDOW_FRAMES = 5
MEMORY_INSTRUCTION = (
    "These videos are earlier moments of this same film. Keep the people, clothing, "
    "setting, lighting and style they show. The camera, framing and action of this "
    "clip follow its own description; do not replay those moments."
)


def memory_entries(clip_item):
    """Normalised memory entries of one clip (invalid rows are rejected loudly)."""
    rows = clip_item.get("memory") or []
    if not isinstance(rows, list):
        raise ValueError("Clip memory must be a list.")
    out = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("clip_id"):
            raise ValueError("Each clip memory needs a source clip.")
        if row.get("enabled", True) is False:
            continue
        start = float(row.get("start") or 0.0)
        end = row.get("end")
        end = None if end in (None, "") else float(end)
        if not math.isfinite(start) or start < 0 or (end is not None and (not math.isfinite(end) or end <= start)):
            raise ValueError("Clip memory ranges need 0 <= start < end.")
        out.append({"clip_id": str(row["clip_id"]), "start": start, "end": end,
                    "note": " ".join(str(row.get("note") or "").split())[:200]})
    if len(out) > MEMORY_LIMIT:
        raise ValueError(f"A clip can remember at most {MEMORY_LIMIT} moments.")
    return out


def memory_windows(clip_item, clips, clip_idx, load_frames, trim_prefix=lambda clip_id: 0):
    """Frame windows for one clip's memory entries.

    ``load_frames(clip_id)`` returns the clip's saved frames ``[T, H, W, C]`` or
    None. ``trim_prefix(clip_id)`` is the hidden continuity overlap at the start
    of those frames, which is not part of the visible clip.
    """
    entries = memory_entries(clip_item)
    order = {str(c.get("id")): i for i, c in enumerate(clips)}
    names = {str(c.get("id")): c.get("name") or c.get("id") for c in clips}
    windows = []
    for entry in entries:
        source = entry["clip_id"]
        name = names.get(source, source)
        if source not in order:
            raise ValueError(f"Clip memory points to a clip that is no longer in the timeline ({source}).")
        if order[source] >= clip_idx:
            raise ValueError(f"Clip memory can only use earlier clips; '{name}' is not before this clip.")
        frames = load_frames(source)
        if frames is None:
            raise ValueError(f"Clip memory needs '{name}' to be generated first.")
        visible = frames[int(trim_prefix(source) or 0):]
        total = int(visible.shape[0])
        first = min(total, max(0, round(entry["start"] * FPS)))
        last = total if entry["end"] is None else min(total, max(first, round(entry["end"] * FPS)))
        count = last - first
        if count < MIN_WINDOW_FRAMES:
            raise ValueError(f"The remembered part of '{name}' is too short; choose at least {MIN_WINDOW_FRAMES} frames (about 0.2 seconds).")
        count = align_frame_count(count, "down")
        window = visible[first:first + count].clone()
        # Saved takes may be 8-bit; reference videos are float pixels in 0..1.
        window = window.float() / 255.0 if not window.is_floating_point() else window.float()
        windows.append({"clip_id": source, "name": name, "note": entry["note"],
                        "start": first / FPS, "end": (first + count) / FPS, "frames": window})
    return windows


def memory_note(windows, first_video):
    """The prompt text that introduces memory videos ``first_video``, ``first_video + 1``..."""
    if not windows:
        return ""
    lines = []
    for offset, window in enumerate(windows):
        detail = window.get("note") or window.get("name") or "an earlier clip"
        lines.append(f"<Video {first_video + offset}> is an earlier moment of this film ({detail}).")
    return "\n".join([*lines, MEMORY_INSTRUCTION])


def filmstrip(frames, trim_prefix=0, count=8, height=64, quality=80):
    """A JPEG strip of ``count`` evenly spaced visible frames, for the memory picker."""
    import io
    import numpy as np
    from PIL import Image
    visible = frames[int(trim_prefix or 0):]
    total = int(visible.shape[0])
    if total < 1:
        raise ValueError("This clip has no visible frames.")
    count = max(1, min(int(count), 16, total))
    height = max(24, min(int(height), 160))
    tiles = []
    for i in range(count):
        index = min(total - 1, int((i + 0.5) * total / count))
        pixels = visible[index].float()
        if not visible.is_floating_point():
            pixels = pixels / 255.0
        array = (pixels.clamp(0, 1).numpy() * 255).astype(np.uint8)
        tile = Image.fromarray(array[..., :3])
        tiles.append(tile.resize((max(1, round(tile.width * height / tile.height)), height), Image.BILINEAR))
    strip = Image.new("RGB", (sum(t.width for t in tiles), height))
    x = 0
    for tile in tiles:
        strip.paste(tile, (x, 0)); x += tile.width
    out = io.BytesIO()
    strip.save(out, "JPEG", quality=quality)
    return out.getvalue()


_SUBJECTS = re.compile(r"^[ \t]*subject_definitions[ \t]*:[ \t]*\n?", re.I | re.M)
_NEXT_SECTION = re.compile(
    r"^[ \t]*(summary|retention_analysis|detailed_description|integrated_multimodal_description|"
    r"overall_soundscape|non_diegetic_music)[ \t]*:", re.I | re.M)
_FIRST_SHOT = re.compile(r"^[ \t]*\[Shot 1\]", re.I | re.M)


def inject_memory_note(prompt, note):
    """Put the memory note where H3 reads reference roles.

    Inside ``subject_definitions`` when the prompt has it, else just before
    ``[Shot 1]``, else at the start.
    """
    prompt = str(prompt or "")
    if not note:
        return prompt
    subjects = _SUBJECTS.search(prompt)
    if subjects:
        following = _NEXT_SECTION.search(prompt, subjects.end())
        cut = following.start() if following else len(prompt)
        body = prompt[subjects.end():cut].rstrip("\n")
        joined = f"{body}\n{note}" if body.strip() else note
        return prompt[:subjects.end()] + joined + "\n\n" + prompt[cut:].lstrip("\n")
    shot = _FIRST_SHOT.search(prompt)
    if shot:
        return prompt[:shot.start()] + note + "\n\n" + prompt[shot.start():]
    return f"{note}\n\n{prompt}".strip()
