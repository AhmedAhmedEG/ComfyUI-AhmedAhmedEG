"""Lazy, revision-addressed previews from completed shot caches, without sampling."""
from __future__ import annotations
import hashlib
import json
import os
import tempfile
from pathlib import Path

from .cache_manager import ProjectCacheManager, safe_component
from .media_io import resolve_input_path


def create_preview_plan(state, scope="latest", base_dir=None, quality="original", take_id=None):
    if scope not in ("latest", "full", "take"):
        raise ValueError("Preview scope must be latest, full or take.")
    if quality not in ("original", "540p", "720p", "1080p"):
        raise ValueError("Unknown preview resolution.")
    manager = ProjectCacheManager(safe_component(state["project_id"]), base_dir)
    shots = state.get("clips", [])
    if not isinstance(shots, list) or len(shots) > 1000:
        raise ValueError("Invalid preview timeline.")
    rows = []
    if scope == "take":
        take = manager._manifest.get("takes", {}).get(safe_component(take_id)) if take_id else None
        shots_to_read = [{"id": take["clip_id"], "name": next((s.get("name") for s in shots if s.get("id") == take["clip_id"]), take["clip_id"])}] if take else []
    else:
        shots_to_read = shots
    for index, shot in enumerate(shots_to_read):
        cid = safe_component(shot.get("id", f"clip_{index+1}"))
        meta = take if scope == "take" else manager._manifest.get("clips", {}).get(cid, {})
        if not meta.get("has_frames"):
            source = shot.get("source")
            if scope == "full" and shot.get("locked") and source and (isinstance(source, str) or source.get("filename") and not source.get("ref_id")):
                rows.append({"clip_id": cid, "name": shot.get("name", cid), "source": shot,
                             "updated_at": 0, "trim_prefix": 0, "index": index})
            continue
        generation = meta.get("generation")
        rows.append({"clip_id": cid, "name": shot.get("name", cid),
            "frames": os.path.basename(manager._clip_artifact_path(cid, "frames", generation)),
            "audio": os.path.basename(manager._clip_artifact_path(cid, "audio", generation)) if meta.get("has_audio") else None,
            "generation": generation, "updated_at": meta.get("updated_at", 0),
            "trim_prefix": int(meta.get("trim_prefix", 0)), "previous_trim": int(meta.get("previous_trim", 0)),
            "index": index})
    if scope == "latest":
        rows = [max(rows, key=lambda row: row["updated_at"])] if rows else []
    if not rows:
        return {"found": False, "scope": scope}
    # Trim a predecessor's handoff only when its immediate successor is present.
    for left, right in zip(rows, rows[1:]):
        if right.get("index", -2) == left.get("index", -1) + 1:
            left["trim_tail"] = right.get("previous_trim", 0)
    plan = {"version": 2, "project_id": manager.project_id, "scope": scope, "quality": quality, "rows": rows,
        "source_state": {k: state[k] for k in ("width", "height", "resolution", "references") if k in state},
        "gain_match": bool(state.get("audio_gain_match", True)), "fade_ms": float(state.get("audio_fade_ms", 15))}
    key = hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    folder = Path(manager.project_dir) / "previews"
    folder.mkdir(exist_ok=True)
    destination = folder / (key + ".json")
    if not destination.exists():
        fd, temporary = tempfile.mkstemp(dir=folder, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                json.dump(plan, output)
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)
    return {"found": True, "scope": scope, "key": key, "project_id": manager.project_id,
        "clip_ids": [row["clip_id"] for row in rows], "clip_count": len(rows), "total_clips": len(shots),
        "missing_clips": [{"id": s["id"], "name": s.get("name", s["id"])} for s in shots if s.get("id") not in {row["clip_id"] for row in rows}] if scope == "full" else [],
        "label": rows[0]["name"] if scope != "full" else f"{len(rows)}/{len(shots)} completed clips"}


def preview_path(project_id, key, base_dir=None):
    import re
    if not re.fullmatch(r"[0-9a-f]{64}", key):
        raise ValueError("Invalid preview revision.")
    manager = ProjectCacheManager(safe_component(project_id), base_dir)
    return manager, Path(manager.project_dir) / "previews" / (key + ".mp4")


def encode_preview(project_id, key, base_dir=None):
    """Encode only the requested revision; iterate frames one shot at a time."""
    import numpy as np
    import torch
    import torch.nn.functional as F
    from .audio_post import concatenate_audio_clips
    from .vendor.dasiwa.helper_pyav_video import encode_attempt
    manager, target = preview_path(project_id, key, base_dir)
    if target.is_file(): return str(target)
    plan_path = resolve_input_path(key + ".json", str(target.parent))
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))

    def load(row):
        if row.get("source"):
            from .source_media import source_range
            source = source_range(row["source"], plan["source_state"], 960, 544, preserve_canvas=True)
            if source is None: raise ValueError("Source clip is unavailable.")
            frames, audio = source["frames"], source["audio"]
        else:
            frames = torch.load(resolve_input_path(row["frames"], manager.project_dir), map_location="cpu", weights_only=True)
            audio = torch.load(resolve_input_path(row["audio"], manager.project_dir), map_location="cpu", weights_only=True) if row.get("audio") else None
        count = int(frames.shape[0])
        start = max(0, int(row.get("trim_prefix", 0)))
        end = count - max(0, int(row.get("trim_tail", 0)))
        if end <= start: raise ValueError("Cached clip has no visible frames after context trimming.")
        frames = frames[start:end]
        if audio:
            rate = int(audio["sample_rate"])
            waveform = audio["waveform"][..., round(start/24*rate):round(end/24*rate)]
            expected = round((end-start)/24*rate)
            if waveform.shape[-1] < expected:
                waveform = F.pad(waveform, (0, expected-waveform.shape[-1]))
            audio = {**audio, "waveform": waveform}
        return frames, audio

    width, height = 0, 0
    audios = []
    def frames_iter():
        for row in plan["rows"]:
            frames, _ = load(row)
            for image in frames:
                image = image[..., :3].permute(2, 0, 1).unsqueeze(0)
                if image.shape[-2:] != (height, width):
                    # Letterbox mixed canvases rather than stretching subjects.
                    ih, iw = image.shape[-2:]; scale = min(width/iw, height/ih)
                    rh, rw = max(1, round(ih*scale)), max(1, round(iw*scale))
                    image = F.interpolate(image, size=(rh, rw), mode="bilinear", align_corners=False)
                    image = F.pad(image, ((width-rw)//2, width-rw-(width-rw)//2, (height-rh)//2, height-rh-(height-rh)//2))
                yield (image[0].permute(1, 2, 0).clamp(0, 1).numpy()*255).round().astype(np.uint8)

    # Audio is prepared first so the shared encoder can configure its stream.
    for row in plan["rows"]:
        frames, audio = load(row)
        height, width = max(height, int(frames.shape[1])), max(width, int(frames.shape[2]))
        if audio is None or audio["waveform"].shape[-1] == 0:
            audio = {"waveform": torch.zeros((1, 2, round(frames.shape[0]/24*48000))), "sample_rate": 48000}
        audios.append(audio)
        del frames
    quality = plan.get("quality", "540p")
    cap = {"540p": (960, 540), "720p": (1280, 720), "1080p": (1920, 1080)}.get(quality)
    ratio = min(1., cap[0]/width, cap[1]/height) if cap else 1.
    width, height = max(2, int(width*ratio)//2*2), max(2, int(height*ratio)//2*2)
    sound = concatenate_audio_clips(audios, target_sample_rate=48000, crossfade_ms=0,
        enable_gain_match=plan["gain_match"], enable_declick=plan["fade_ms"] > 0, seam_fade_ms=plan["fade_ms"])
    audios.clear()
    encode_attempt(str(target), "MP4", "libx264", width, height, 24, 8, 23, frames_iter,
        audio=(sound["waveform"][0].numpy(), sound["sample_rate"]), audio_encoder="aac", audio_bitrate="128k")
    return str(target)
