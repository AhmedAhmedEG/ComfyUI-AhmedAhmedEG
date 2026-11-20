"""Lazy, revision-addressed previews from completed shot caches, without sampling."""
from __future__ import annotations
import hashlib
import json
import os
import tempfile
from pathlib import Path

from .cache_manager import ProjectCacheManager, safe_component, load_frame_tensor
from .media_io import resolve_input_path


def _clean_clip_ids(clip_ids):
    return [safe_component(str(c)) for c in (clip_ids or []) if str(c or '').strip()][:1000]


def available_streams(manifest):
    """Stages that actually exist in this project's saved results, in display order."""
    clips = manifest.get("clips", {}) or {}
    out = ["final"]
    if any((v or {}).get("has_frames") for v in (manifest.get("first_pass", {}) or {}).values()):
        out.append("first_pass")
    if any((v or {}).get("has_pre_refine") for v in clips.values()):
        out.append("pre_refine")
    passes = sorted({int(r["pass"]) for v in clips.values() for r in (v or {}).get("refine_passes", []) or [] if str(r.get("pass", "")).isdigit()})
    out.extend(f"pass:{n}" for n in passes)
    return out


def cached_preview_plan(project_id, scope='latest', base_dir=None, quality='original', stream='final', clip_ids=None):
    """Restore only existing encodes. Opening a viewer must not create cache files."""
    from types import SimpleNamespace
    from .cache_manager import get_cache_root_dir
    from .preview_segments import playback_manifest
    project_id = safe_component(project_id)
    folder = Path(base_dir or get_cache_root_dir(create=False)) / project_id / 'previews'
    candidates = sorted(folder.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True) if folder.is_dir() else []
    manager = SimpleNamespace(project_id=project_id, project_dir=str(folder.parent))
    for path in candidates:
        try:
            plan = json.loads(path.read_text(encoding='utf-8'))
            if any(plan.get(k) != v for k,v in [('project_id',project_id),('scope',scope),('quality',quality),('stream',stream)]):
                continue
            if scope == 'clips' and plan.get('clip_ids') != _clean_clip_ids(clip_ids):
                continue
            playback = None
            try: playback = playback_manifest(manager, plan, read_only=True)
            except (FileNotFoundError, ValueError, KeyError): pass
            if playback is None and not path.with_suffix('.mp4').is_file():
                continue
            rows = plan.get('rows', [])
            return {'found':True, 'cache_read_only':True, 'project_id':project_id,
                'scope':scope, 'stream':stream, 'key':path.stem, 'playback':playback,
                'clip_ids':[row['clip_id'] for row in rows], 'clip_count':len(rows),
                'label':'Saved preview · waiting for Master output'}
        except (OSError, ValueError, TypeError, KeyError):
            continue
    return {'found':False, 'cache_read_only':True, 'scope':scope,
        'label':'Waiting for Master output. Existing preview caches are kept.'}


def create_preview_plan(state, scope="latest", base_dir=None, quality="original", stream="final", run_context=None, clip_ids=None):
    """scope: "latest" (newest saved clip), "full" (every saved clip) or "clips" (the chosen ``clip_ids``)."""
    if scope not in ("latest", "full", "clips"):
        raise ValueError("Preview scope must be latest, full or clips.")
    if quality not in ("original", "540p", "720p", "1080p"):
        raise ValueError("Unknown preview resolution.")
    if stream not in ("final","first_pass","pre_refine") and not (stream.startswith("pass:") and stream[5:].isdigit()):
        raise ValueError("Unknown preview stream.")
    manager = ProjectCacheManager(safe_component(state["project_id"]), base_dir)
    shots = state.get("clips", [])
    if not isinstance(shots, list) or len(shots) > 1000:
        raise ValueError("Invalid preview timeline.")
    rows = []
    chosen = _clean_clip_ids(clip_ids)
    shots_to_read = shots
    statuses = []
    live = run_context
    for index, shot in enumerate(shots_to_read):
        cid = safe_component(shot.get("id", f"clip_{index+1}"))
        meta = manager._manifest.get("clips", {}).get(cid, {})
        status = {"id": cid, "name": shot.get("name", cid), "index": index, "ready": False}
        statuses.append(status)
        frames_kind="frames";audio_kind="audio";direct_frames=direct_audio=None
        if stream=="first_pass":
            meta=manager._manifest.get("first_pass",{}).get(cid,{})
            frames_kind,audio_kind="draft_frames","draft_audio"
        elif stream=="pre_refine":
            if not meta.get("has_pre_refine"): continue
            frames_kind="pre_refine"
        elif stream.startswith("pass:"):
            entry=next((r for r in meta.get("refine_passes",[]) if r["pass"]==int(stream[5:])),None)
            if entry is None: continue
            direct_frames,direct_audio=entry["frames"],entry["audio"]
        # Approval controls Master regeneration, not saved-result visibility.
        # Queuing/sampling a replacement never hides the current saved result.
        # store_clip_results publishes its replacement and removes dependent
        # cached results together, only after a successful save.
        if not meta.get("has_frames"):
            source = shot.get("source")
            if scope == "full" and shot.get("locked") and source and (isinstance(source, str) or source.get("filename") and not source.get("ref_id")):
                status["ready"] = True
                rows.append({"clip_id": cid, "name": shot.get("name", cid), "source": shot,
                             "updated_at": 0, "trim_prefix": 0, "index": index})
            continue
        generation = meta.get("generation")
        status["ready"] = True
        rows.append({"clip_id": cid, "name": shot.get("name", cid),
            "frames": direct_frames or os.path.basename(manager._clip_artifact_path(cid, frames_kind, generation)),
            "audio": direct_audio or (os.path.basename(manager._clip_artifact_path(cid, audio_kind, generation)) if meta.get("has_audio") else None),
            "generation": generation, "updated_at": meta.get("updated_at", 0),
            "frame_count": meta.get('frame_count') if stream == 'final' else None,
            "trim_prefix": int(meta.get("trim_prefix", 0)), "previous_trim": int(meta.get("previous_trim", 0)),
            "index": index})
    if scope == "latest":
        rows = [max(rows, key=lambda row: row["updated_at"])] if rows else []
    elif scope == "clips":
        rows = [row for row in rows if row["clip_id"] in chosen]
    common = {"clips": statuses, "streams": available_streams(manager._manifest)}
    if not rows:
        label = ("None of the chosen clips has a saved result at this stage." if scope == "clips" and chosen
                 else "Choose one or more clips." if scope == "clips" else "No completed clips yet. Generate a shot first.")
        return {"found": False, "scope": scope, "run_active": live is not None,
                "project_id": manager.project_id, "stream": stream,
                "invalidated_clip_ids": manager._manifest.get('invalidated_clips', []),
                "label": label, **common}
    # Trim a predecessor's handoff only when its immediate successor is present.
    for left, right in zip(rows, rows[1:]):
        if right.get("index", -2) == left.get("index", -1) + 1:
            trim = int(right.get("previous_trim", 0) or 0)
            # A kept successor's handoff can be stale after its predecessor was
            # regenerated shorter; never let it erase the whole predecessor
            # (that made every preview request fail with "no visible frames").
            if left.get("frame_count") is not None:
                trim = min(trim, max(0, int(left["frame_count"]) - int(left.get("trim_prefix", 0)) - 1))
            left["trim_tail"] = trim
    plan = {"version": 6, "project_id": manager.project_id, "scope": scope, "quality": quality, "stream":stream,"rows": rows,
        **({"clip_ids": chosen} if scope == "clips" else {}),
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
    from .preview_segments import playback_manifest
    return {"found": True, "scope": scope, "key": key, "project_id": manager.project_id,
        "playback": playback_manifest(manager, plan),
        "invalidated_clip_ids": manager._manifest.get('invalidated_clips', []),
        "stream": stream, "clip_generations": {row['clip_id']: row.get('generation') for row in rows if row.get('generation')},
        "clip_ids": [row["clip_id"] for row in rows], "clip_count": len(rows), "total_clips": len(shots),
        "missing_clips": [{"id": s["id"], "name": s.get("name", s["id"])} for s in shots if s.get("id") not in {row["clip_id"] for row in rows}] if scope == "full" else [],
        "run_active": live is not None, **common,
        "label": rows[0]["name"] if scope == "latest" else
                 f"{len(rows)}/{len(shots)} completed clips" if scope == "full" else
                 (rows[0]["name"] if len(rows) == 1 else f"{len(rows)} chosen clips")}


def preview_path(project_id, key, base_dir=None):
    import re
    if not re.fullmatch(r"[0-9a-f]{64}", key):
        raise ValueError("Invalid preview revision.")
    manager = ProjectCacheManager(safe_component(project_id), base_dir)
    return manager, Path(manager.project_dir) / "previews" / (key + ".mp4")


def encode_preview(project_id, key, base_dir=None, *, output_path=None):
    """Encode only the requested revision; iterate frames one shot at a time."""
    import numpy as np
    import torch
    import torch.nn.functional as F
    from .audio_post import join_timeline_audio
    from .vendor.dasiwa.helper_pyav_video import encode_attempt
    manager, cached_target = preview_path(project_id, key, base_dir)
    target=Path(output_path) if output_path is not None else cached_target
    if target.is_file(): return str(target)
    plan_path = resolve_input_path(key + ".json", str(cached_target.parent))
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))

    def load(row):
        if row.get("source"):
            from .source_media import source_range
            source = source_range(row["source"], plan["source_state"], 960, 544, preserve_canvas=True)
            if source is None: raise ValueError("Source clip is unavailable.")
            frames, audio = source["frames"], source["audio"]
        else:
            frames = load_frame_tensor(resolve_input_path(row["frames"], manager.project_dir))
            audio = torch.load(resolve_input_path(row["audio"], manager.project_dir), map_location="cpu", weights_only=True) if row.get("audio") else None
        count = int(frames.shape[0])
        start = max(0, int(row.get("trim_prefix", 0)))
        end = count - max(0, int(row.get("trim_tail", 0)))
        if end <= start: raise ValueError("Cached clip has no visible frames after context trimming.")
        frames = frames[start:end]
        if audio:
            from .audio_post import slice_audio_frames
            audio = slice_audio_frames(audio, start, end)
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
    for index, row in enumerate(plan["rows"]):
        frames, audio = load(row)
        height, width = max(height, int(frames.shape[1])), max(width, int(frames.shape[2]))
        if audio is None or audio["waveform"].shape[-1] == 0:
            audio = {"waveform": torch.zeros((1, 2, round(frames.shape[0]/24*48000))), "sample_rate": 48000}
        if index == 0 or row['index'] != plan['rows'][index-1]['index'] + 1:
            audio.pop('seam_prefix', None)
        audios.append(audio)
        del frames
    quality = plan.get("quality", "540p")
    cap = {"540p": (960, 540), "720p": (1280, 720), "1080p": (1920, 1080)}.get(quality)
    ratio = min(1., cap[0]/width, cap[1]/height) if cap else 1.
    width, height = max(2, int(width*ratio)//2*2), max(2, int(height*ratio)//2*2)
    sound = join_timeline_audio(audios, fade_ms=plan['fade_ms'], enable_gain_match=plan['gain_match'])
    audios.clear()
    fd, temporary = tempfile.mkstemp(suffix='.mp4', dir=target.parent)
    os.close(fd)
    try:
        encode_attempt(temporary, "MP4", "libx264", width, height, 24, 8, 23, frames_iter,
            audio=(sound["waveform"][0].numpy(), sound["sample_rate"]), audio_encoder="aac", audio_bitrate="128k")
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
    return str(target)
