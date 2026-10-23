"""Server-side latent caching, validation chains, and lightweight project serialization."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import zipfile
import re
import tempfile
import threading
import uuid
import shutil
from functools import wraps
from typing import Any, Dict, List, Optional

import torch

from .config import PROJECT_FORMAT, PROJECT_FORMAT_VERSION

log = logging.getLogger("MiniMaxH3MasterDirector.cache")
_LOCKS = {}
_LOCKS_GUARD = threading.Lock()


def portable_tree(value):
    if isinstance(value, torch.Tensor): return value.detach().cpu()
    if getattr(value, "is_nested", False) and hasattr(value, "unbind"):
        return {"_mmx_nested": [portable_tree(part) for part in value.unbind()]}
    if isinstance(value, dict): return {key: portable_tree(item) for key, item in value.items()}
    if isinstance(value, tuple): return tuple(portable_tree(item) for item in value)
    if isinstance(value, list): return [portable_tree(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)): return value
    raise TypeError(f"Unsupported persistent latent metadata: {type(value).__name__}")


def restore_tree(value):
    if isinstance(value, dict) and set(value) == {"_mmx_nested"}:
        import comfy.nested_tensor
        return comfy.nested_tensor.NestedTensor(tuple(restore_tree(part) for part in value["_mmx_nested"]))
    if isinstance(value, dict): return {key: restore_tree(item) for key, item in value.items()}
    if isinstance(value, tuple): return tuple(restore_tree(item) for item in value)
    if isinstance(value, list): return [restore_tree(item) for item in value]
    return value


def _locked(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return call


def safe_component(value: str) -> str:
    """One portable filename component; reject traversal and Windows devices."""
    value = str(value)
    if (not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,127}", value)
            or value.endswith(".") or
            value.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}):
        raise ValueError(f"Invalid cache identifier: {value!r}")
    return value


def load_frame_tensor(path, mmap=True):
    """Keep saved video pixels reclaimable by the OS, rather than copying to RAM."""
    try:
        return torch.load(path, map_location='cpu', weights_only=True, mmap=mmap)
    except RuntimeError as exc:
        # Imported legacy torch archives cannot be memory-mapped. Our own
        # atomic_save uses the modern ZIP format; never retry genuine OOMs.
        if not mmap or 'mmap can only be used with files saved with' not in str(exc):
            raise
        return torch.load(path, map_location='cpu', weights_only=True)


def fingerprint_value(value) -> str:
    """Hash nested settings and actual media contents, preserving reference order."""
    h = hashlib.sha256()
    def visit(item):
        if isinstance(item, dict):
            h.update(b"dict")
            for key in sorted(item, key=str):
                visit(str(key))
                visit(item[key])
        elif isinstance(item, (list, tuple)):
            h.update(b"list")
            for child in item:
                visit(child)
        elif isinstance(item, torch.Tensor):
            tensor = item.detach() if hasattr(item, "detach") else item
            tensor = tensor.cpu().contiguous() if hasattr(tensor, "contiguous") else tensor.cpu()
            h.update(str((tuple(tensor.shape), tensor.dtype)).encode())
            # Float conversion also supports bfloat16, which NumPy cannot represent.
            h.update(tensor.float().numpy().tobytes() if hasattr(tensor, "numpy") else tensor.tobytes())
        elif item is None or isinstance(item, (str, int, float, bool)):
            h.update(json.dumps(item, ensure_ascii=False, allow_nan=False).encode())
            h.update(b"\0")
        else:
            provenance = getattr(item, "_mmx_provenance", None)
            if isinstance(provenance, dict):
                visit(provenance)
                patcher = getattr(item, "patcher", item)
                patches = getattr(patcher, "patches", None)
                if isinstance(patches, dict): visit(patches)
                return
            # Unknown live objects cannot safely share a persistent cache entry.
            h.update(f"{type(item).__module__}.{type(item).__name__}:{id(item)}".encode())
            patcher = getattr(item, "patcher", item)
            revision = getattr(patcher, "patches_uuid", None)
            if revision is not None and type(revision).__module__ != "unittest.mock":
                h.update(str(revision).encode())
    visit(value)
    return h.hexdigest()


def get_cache_root_dir(create=True) -> str:
    """Resolve ComfyUI output cache directory."""
    try:
        import folder_paths
        output_dir = folder_paths.get_output_directory()
    except Exception:
        output_dir = "output"

    cache_dir = os.path.join(output_dir, "minimax_cache")
    if create:
        os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def compute_clip_fingerprint(
    prompt: str,
    duration: float,
    width: int,
    height: int,
    seed: int,
    model_name: str = "",
    loras: Optional[List[Dict[str, Any]]] = None,
    ref_signatures: Optional[List[str]] = None,
    upstream_fingerprint: Optional[str] = None,
    generation_settings: Optional[Dict[str, Any]] = None,
) -> str:
    """Compute a deterministic hash fingerprint representing a clip's exact generation inputs."""
    h = hashlib.sha256()
    h.update(str(prompt or "").strip().encode("utf-8"))
    h.update(f"|{duration!r}|{width}|{height}|{seed}|{model_name}".encode("utf-8"))

    if loras:
        for item in sorted(loras, key=lambda x: x.get("name", "")):
            h.update(fingerprint_value(item).encode())

    if ref_signatures:
        for sig in ref_signatures:
            h.update(f"|ref:{sig}".encode("utf-8"))

    if upstream_fingerprint:
        h.update(f"|upstream:{upstream_fingerprint}".encode("utf-8"))

    if generation_settings is not None:
        h.update(fingerprint_value(generation_settings).encode())

    return h.hexdigest()[:24]


class ProjectCacheManager:
    """Manages disk-cached latents, validation state, and lightweight project archives."""

    def __init__(self, project_id: str = "default", base_dir: Optional[str] = None):
        self.project_id = safe_component(project_id or "default")
        root = base_dir or get_cache_root_dir()
        self.project_dir = os.path.join(root, self.project_id)
        with _LOCKS_GUARD:
            self._lock = _LOCKS.setdefault(os.path.realpath(self.project_dir), threading.RLock())
        os.makedirs(self.project_dir, exist_ok=True)
        self.manifest_path = os.path.join(self.project_dir, "manifest.json")
        self._manifest = self._load_manifest()

    def _load_manifest(self) -> Dict[str, Any]:
        if os.path.isfile(self.manifest_path):
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and isinstance(data.get("clips"), dict):
                        return data
            except Exception:
                pass
        return {"project_id": self.project_id, "updated_at": time.time(), "clips": {}}

    @_locked
    def save_manifest(self):
        self._manifest["updated_at"] = time.time()
        fd, tmp_path = tempfile.mkstemp(dir=self.project_dir, suffix=".json.tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._manifest, f, indent=2)
            os.replace(tmp_path, self.manifest_path)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def get_clip_latent_path(self, clip_id: str) -> str:
        return self._clip_artifact_path(clip_id, "latent")

    def get_clip_audio_path(self, clip_id: str) -> str:
        return self._clip_artifact_path(clip_id, "audio")

    def get_clip_frames_path(self, clip_id: str) -> str:
        return self._clip_artifact_path(clip_id, "frames")

    def _clip_artifact_path(self, clip_id, kind, generation=None):
        clip_id = safe_component(clip_id)
        if generation is None:
            generation = self._manifest.get("clips", {}).get(clip_id, {}).get("generation")
        suffix = "_" + safe_component(generation) if generation else ""
        return os.path.join(self.project_dir, f"clip_{clip_id}{suffix}_{kind}.pt")

    def _result_files(self, clip_id, meta, draft=False):
        """Enumerate only this pack's artifacts; never follow manifest paths outside the project."""
        files = set()
        token = meta.get('generation')
        kinds = ('draft','draft_frames','draft_audio') if draft else ('latent','audio','frames','pre_refine','source_frames','source_audio')
        for kind in kinds:
            files.add(os.path.basename(self._clip_artifact_path(clip_id, kind, token)))
        if not draft:
            for row in meta.get('refine_passes', []):
                files.update(row[key] for key in ('frames','audio') if isinstance(row.get(key), str))
            if meta.get('first_pass'):
                files.update(self._result_files(clip_id, meta['first_pass'], draft=True))
        return files

    def _prune_files(self, candidates):
        active = set()
        for cid, meta in self._manifest.get('clips', {}).items():
            active.update(self._result_files(cid, meta))
        for cid, meta in self._manifest.get('first_pass', {}).items():
            active.update(self._result_files(cid, meta, draft=True))
        pending = []
        removed = 0
        for name in {name for name in (*candidates, *self._manifest.get('pending_prune', [])) if isinstance(name, str)}:
            if name in active or not isinstance(name, str) or os.path.basename(name) != name or not re.fullmatch(r'clip_[A-Za-z0-9_.-]+_(?:latent|audio|frames|pre_refine|source_frames|source_audio|draft|draft_frames|draft_audio|pass_frames|pass_audio)\.pt', name):
                continue
            path = os.path.join(self.project_dir, name)
            if os.path.realpath(os.path.dirname(path)) != os.path.realpath(self.project_dir) or os.path.islink(path):
                continue
            try:
                os.unlink(path); removed += 1
            except FileNotFoundError:
                pass
            except OSError:
                pending.append(name)  # Windows may still have an old mapped preview open.
        if pending:
            self._manifest['pending_prune'] = pending
        else:
            self._manifest.pop('pending_prune', None)
        return removed

    def _prune_previews(self, include_orphans=False):
        """Discard derived revisions which refer to a replaced generation."""
        folder = os.path.join(self.project_dir, 'previews')
        if not os.path.isdir(folder) or os.path.islink(folder): return
        for name in os.listdir(folder):
            if include_orphans and re.fullmatch(r'[0-9a-f]{64}\.mp4', name):
                media = os.path.join(folder, name)
                if not os.path.exists(media[:-4]+'.json') and not os.path.islink(media):
                    try: os.unlink(media)
                    except OSError: pass
            if not re.fullmatch(r'[0-9a-f]{64}\.json', name): continue
            path = os.path.join(folder, name)
            if os.path.islink(path): continue
            try:
                with open(path, encoding='utf-8') as source: plan = json.load(source)
                obsolete = False
                for row in plan.get('rows', []):
                    if row.get('source'): continue
                    cid = row.get('clip_id')
                    meta = self._manifest.get('first_pass' if plan.get('stream') == 'first_pass' else 'clips', {}).get(cid, {})
                    if row.get('generation') != meta.get('generation'): obsolete = True
                if obsolete:
                    for target in (path, path[:-5]+'.mp4'):
                        if not os.path.islink(target):
                            try: os.unlink(target)
                            except FileNotFoundError: pass
            except (OSError, ValueError, TypeError):
                continue

    @_locked
    def prune_history(self, include_orphans=False):
        """One-time idle migration, or retry cleanup after a successful replacement."""
        self._manifest = self._load_manifest()
        candidates = set()
        for row in self._manifest.pop('takes', {}).values():
            if row.get('clip_id'): candidates.update(self._result_files(row['clip_id'], row))
        if include_orphans:
            candidates.update(name for name in os.listdir(self.project_dir)
                if re.fullmatch(r'clip_[A-Za-z0-9_.-]+_(?:latent|audio|frames|pre_refine|source_frames|source_audio|draft|draft_frames|draft_audio|pass_frames|pass_audio)\.pt', name))
        self.save_manifest()  # Stop exposing history before unlinking its artifacts.
        count = self._prune_files(candidates)
        self._prune_previews(include_orphans=include_orphans)
        self.save_manifest()
        return count

    def load_clip_pre_refine(self, clip_id):
        if not self._manifest.get("clips", {}).get(clip_id, {}).get("has_pre_refine"):
            return None
        return self._load_tensor_file(self._clip_artifact_path(clip_id, "pre_refine"), mmap=True)

    @_locked
    def is_clip_cached_and_valid(self, clip_id: str, current_fingerprint: str) -> bool:
        """Check if clip has stored latents on disk matching the exact fingerprint."""
        self._manifest = self._load_manifest()
        clip_meta = self._manifest.get("clips", {}).get(clip_id)
        if not clip_meta:
            return False

        if clip_meta.get("fingerprint") != current_fingerprint:
            return False

        latent_path = self.get_clip_latent_path(clip_id)
        return os.path.isfile(latent_path)

    @_locked
    def begin_preview_run(self):
        """Track fresh reviewable results; the current clip remains until replacement succeeds."""
        self._manifest = self._load_manifest()
        self._preview_run_id = uuid.uuid4().hex
        self._manifest['preview_run_id'] = self._preview_run_id
        self.save_manifest()

    @_locked
    def store_clip_results(
        self,
        clip_id: str,
        fingerprint: str,
        latent_dict: Optional[Dict[str, Any]],
        audio_dict: Optional[Dict[str, Any]] = None,
        decoded_frames: Optional[torch.Tensor] = None,
        validated: bool = True,
        pre_refine_frames=None,
        invalidate_clip_ids=(),
    ):
        """Save clip latent, audio, and frames to server disk cache."""
        self._manifest = self._load_manifest()
        previous = self._manifest.get('clips', {}).get(clip_id, {})
        obsolete = self._result_files(clip_id, previous) if previous else set()
        for row in self._manifest.pop('takes', {}).values():
            if row.get('clip_id'): obsolete.update(self._result_files(row['clip_id'], row))
        generation = uuid.uuid4().hex
        latent_path = self._clip_artifact_path(clip_id, "latent", generation)
        try:
            if latent_dict is not None:
                from .continuity import unpack_av_samples
                streams, nested = unpack_av_samples(latent_dict["samples"])
                portable = dict(latent_dict)
                portable["samples"] = tuple(s.cpu() for s in streams) if nested else streams[0].cpu()
                self._atomic_save(portable_tree(portable), latent_path)

            if audio_dict is not None:
                audio_path = self._clip_artifact_path(clip_id, "audio", generation)
                self._atomic_save({**audio_dict, "waveform": audio_dict["waveform"].cpu()}, audio_path)

            if decoded_frames is not None:
                frames_path = self._clip_artifact_path(clip_id, "frames", generation)
                self._atomic_save(decoded_frames.cpu(), frames_path)
            if pre_refine_frames is not None:
                self._atomic_save(pre_refine_frames.cpu(), self._clip_artifact_path(clip_id, "pre_refine", generation))

            if "clips" not in self._manifest:
                self._manifest["clips"] = {}

            self._manifest["clips"][clip_id] = {
                "fingerprint": fingerprint,
                "validated": bool(validated),
                "updated_at": time.time(),
                "has_audio": audio_dict is not None,
                "has_latent": latent_dict is not None,
                "has_frames": decoded_frames is not None,
                "width": int(decoded_frames.shape[2]) if decoded_frames is not None else None,
                "height": int(decoded_frames.shape[1]) if decoded_frames is not None else None,
                "frame_count": int(decoded_frames.shape[0]) if decoded_frames is not None else None,
                "generation": generation,
                "preview_run_id": getattr(self, "_preview_run_id", None),
                "has_pre_refine": pre_refine_frames is not None,
            }
            invalidated = {safe_component(cid) for cid in invalidate_clip_ids} - {clip_id}
            for cid in invalidated:
                old = self._manifest.get('clips', {}).pop(cid, None)
                if old: obsolete.update(self._result_files(cid, old))
                draft = self._manifest.get('first_pass', {}).pop(cid, None)
                if draft: obsolete.update(self._result_files(cid, draft, draft=True))
            self._manifest['invalidated_clips'] = sorted(
                (set(self._manifest.get('invalidated_clips', [])) | invalidated) - {clip_id})
            self.save_manifest()
        except Exception:
            self._manifest = self._load_manifest()
            self._prune_files(self._result_files(clip_id, {'generation':generation}))
            raise
        self._prune_files(obsolete)
        self._prune_previews()
        self.save_manifest()

    def load_clip_latent(self, clip_id: str) -> Optional[Dict[str, Any]]:
        latent_path = self.get_clip_latent_path(clip_id)
        if os.path.isfile(latent_path):
            try:
                data = restore_tree(torch.load(latent_path, map_location="cpu", weights_only=True))
                if isinstance(data.get("samples"), (tuple, list)):
                    from .continuity import repack_av_latent
                    data["samples"] = repack_av_latent(*data["samples"])["samples"]
                return data
            except Exception as exc:
                log.warning("Ignoring unreadable latent cache %s: %s", clip_id, exc)
        return None

    def load_clip_audio(self, clip_id: str) -> Optional[Dict[str, Any]]:
        audio_path = self.get_clip_audio_path(clip_id)
        if os.path.isfile(audio_path):
            try:
                return torch.load(audio_path, map_location="cpu", weights_only=True)
            except Exception as exc:
                log.warning("Ignoring unreadable audio cache %s: %s", clip_id, exc)
        return None

    def load_clip_frames(self, clip_id: str, mmap: bool = True) -> Optional[torch.Tensor]:
        frames_path = self.get_clip_frames_path(clip_id)
        if os.path.isfile(frames_path):
            try:
                return load_frame_tensor(frames_path, mmap=mmap)
            except Exception as exc:
                log.warning("Ignoring unreadable frames cache %s: %s", clip_id, exc)
        return None

    @staticmethod
    def _load_tensor_file(path, mmap=False):
        if not os.path.isfile(path): return None
        if mmap: return load_frame_tensor(path)
        return torch.load(path, map_location="cpu", weights_only=True)

    @_locked
    def result_availability(self):
        """Small filesystem-backed status; never loads large tensors for UI polling."""
        self._manifest = self._load_manifest()
        rows = {}
        for cid, meta in self._manifest.get("clips", {}).items():
            frames = os.path.isfile(self.get_clip_frames_path(cid))
            audio = os.path.isfile(self.get_clip_audio_path(cid))
            latent = os.path.isfile(self.get_clip_latent_path(cid))
            rows[cid] = {"has_frames": frames, "has_audio": audio, "has_latent": latent,
                         "can_approve": latent or frames and audio, "generation": meta.get("generation")}
        for cid,meta in self._manifest.get("first_pass",{}).items():
            row=rows.setdefault(cid,{"has_frames":False,"has_audio":False,"has_latent":False,"can_approve":False})
            row["has_first_pass"]=os.path.isfile(self._clip_artifact_path(cid,"draft",meta["generation"]))
        return rows

    @_locked
    def restore_clip_media(self, clip_id, frames, audio):
        """Repair preview artifacts from an existing latent without creating a new take."""
        self._manifest = self._load_manifest()
        if clip_id not in self._manifest.get("clips", {}) or not os.path.isfile(self.get_clip_latent_path(clip_id)):
            raise ValueError("Cannot restore media without a saved clip latent.")
        self._atomic_save(frames.cpu(), self.get_clip_frames_path(clip_id))
        self._atomic_save({**audio, "waveform": audio["waveform"].cpu()}, self.get_clip_audio_path(clip_id))
        metadata = {"has_frames": True, "has_audio": True, "width": int(frames.shape[2]), "height": int(frames.shape[1])}
        self._manifest["clips"][clip_id].update(metadata)
        self.save_manifest()

    @_locked
    def update_clip_metadata(self, clip_id, metadata):
        clip_id = safe_component(clip_id)
        self._manifest = self._load_manifest()
        if clip_id not in self._manifest["clips"]:
            raise ValueError("Cannot annotate a missing cached shot.")
        self._manifest["clips"][clip_id].update(metadata)
        if 'first_pass' in metadata:
            if metadata['first_pass'] is None:
                self._manifest.get('first_pass', {}).pop(clip_id, None)
        self.save_manifest()
        if 'first_pass' in metadata:
            self._prune_files(name for name in os.listdir(self.project_dir) if name.startswith('clip_'+clip_id+'_'))
            self._prune_previews()
            self.save_manifest()

    @staticmethod
    def _atomic_save(data, path):
        fd, temporary = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
        os.close(fd)
        try:
            torch.save(data, temporary)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @_locked
    def invalidate_downstream(self, changed_clip_index: int, all_clip_ids: List[str]):
        """Invalidate the changed clip and all subsequent clips in the timeline."""
        self._manifest = self._load_manifest()
        for i in range(changed_clip_index, len(all_clip_ids)):
            cid = all_clip_ids[i]
            if cid in self._manifest.get("clips", {}):
                self._manifest["clips"][cid]["validated"] = False
        self.save_manifest()

    @_locked
    def clear_project_cache(self):
        """Wipe cached latents for this project."""
        # Encoded previews are saved results too. Check the resolved directory
        # before removing it, so a symlink cannot redirect cleanup elsewhere.
        previews = os.path.join(self.project_dir, "previews")
        if os.path.isdir(previews):
            root = os.path.realpath(self.project_dir)
            target = os.path.realpath(previews)
            if os.path.islink(previews) or os.path.commonpath([root, target]) != root or target == root:
                raise ValueError("Preview directory is outside this project's cache.")
            shutil.rmtree(previews)
        for f in os.listdir(self.project_dir):
            p = os.path.join(self.project_dir, f)
            if os.path.isfile(p):
                os.remove(p)
        self._manifest = {"project_id": self.project_id, "updated_at": time.time(), "clips": {}}
        self.save_manifest()

    # --- Lightweight Project Serialization ---

    def export_lightweight_project_data(
        self,
        timeline_state: Dict[str, Any],
        project_name: str = "MyMiniMaxProject",
    ) -> Dict[str, Any]:
        """Produce a pure, lightweight JSON object with zero bulky latents."""
        self._manifest = self._load_manifest()
        cache_refs = {}
        for cid, meta in self._manifest.get("clips", {}).items():
            cache_refs[cid] = {
                "fingerprint": meta.get("fingerprint"),
                "validated": meta.get("validated", False),
            }

        return {
            "format": PROJECT_FORMAT,
            "version": PROJECT_FORMAT_VERSION,
            "project_name": project_name,
            "project_id": self.project_id,
            "created_at": time.time(),
            "timeline": timeline_state,
            "server_cache_manifest": cache_refs,
        }

    def serialize_project(
        self,
        project_id: str,
        clips: List[Dict[str, Any]],
        timeline: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Helper to serialize a project configuration into a lightweight JSON string."""
        data = {
            "format": PROJECT_FORMAT,
            "version": PROJECT_FORMAT_VERSION,
            "project_id": project_id,
            "clips": clips,
            "timeline": timeline,
            "metadata": metadata or {},
        }
        return json.dumps(data, indent=2)

    def export_lightweight_project_archive(
        self,
        timeline_state: Dict[str, Any],
        destination_zip_path: str,
        project_name: str = "MyMiniMaxProject",
    ) -> str:
        """Create a tiny .mmxproj zip archive (under a few hundred kilobytes)."""
        data = self.export_lightweight_project_data(timeline_state, project_name=project_name)
        with zipfile.ZipFile(destination_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("project.json", json.dumps(data, indent=2))
        return destination_zip_path

    def import_lightweight_project_data(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """Restore project timeline settings and reconnect to existing server-side cached latents."""
        if not isinstance(project_data, dict) or project_data.get("format") != PROJECT_FORMAT:
            raise ValueError("Not a MiniMax H3 Master Director project.")
        if project_data.get("version") != PROJECT_FORMAT_VERSION:
            raise ValueError("Unsupported project format version.")
        timeline = project_data.get("timeline")
        if not isinstance(timeline, dict) or not isinstance(timeline.get("clips", []), list):
            raise ValueError("Project timeline must contain a clips list.")
        # Uploaded fingerprints are hints, never proof of server cache contents.
        return {**timeline, "project_id": self.project_id}


    @_locked
    def store_first_pass(self, clip_id, fingerprint, latent, frames, audio, metadata=None):
        self._manifest = self._load_manifest()
        old = self._manifest.get('first_pass', {}).get(clip_id)
        token = uuid.uuid4().hex
        files={kind:self._clip_artifact_path(clip_id,kind,token) for kind in ('draft','draft_frames','draft_audio')}
        try:
            self._atomic_save(portable_tree(latent),files['draft'])
            self._atomic_save(frames.cpu(),files['draft_frames'])
            self._atomic_save(portable_tree(audio),files['draft_audio'])
            row={'fingerprint':fingerprint,'generation':token,'width':int(frames.shape[2]),'height':int(frames.shape[1]),
                 'updated_at':time.time(),'has_frames':True,'has_audio':True,**(metadata or {}),
                 'preview_run_id':getattr(self, '_preview_run_id', None)}
            self._manifest.setdefault('first_pass',{})[safe_component(clip_id)]=row
            self.save_manifest()
        except Exception:
            self._manifest = self._load_manifest()
            self._prune_files(os.path.basename(path) for path in files.values())
            raise
        if old:
            self._prune_files(self._result_files(clip_id, old, draft=True))
            self._prune_previews()
            self.save_manifest()
        return row

    @_locked
    def admit_first_pass(self, clip_id, generation):
        """Make an explicitly reused draft reviewable in this run, without copying tensors."""
        self._manifest = self._load_manifest()
        row = self._manifest.get('first_pass', {}).get(safe_component(clip_id))
        if row is None or row.get('generation') != generation:
            raise ValueError('The staged first pass changed; review the current draft again.')
        row['preview_run_id'] = self._preview_run_id
        self.save_manifest()

    def load_first_pass(self, clip_id, fingerprint=None):
        self._manifest=self._load_manifest()
        row=self._manifest.get('first_pass',{}).get(safe_component(clip_id))
        if not row or fingerprint is not None and row['fingerprint']!=fingerprint: return None
        latent=self._load_tensor_file(self._clip_artifact_path(clip_id,'draft',row['generation']))
        if latent is not None:
            latent=restore_tree(latent)
            if isinstance(latent.get('samples'),(tuple,list)):
                from .continuity import repack_av_latent
                latent['samples']=repack_av_latent(*latent['samples'])['samples']
        return {**row,'latent':latent} if latent is not None else None

    def store_refine_pass(self, clip_id, number, frames, audio):
        token=uuid.uuid4().hex
        frames_path=self._clip_artifact_path(clip_id,'pass_frames',token)
        audio_path=self._clip_artifact_path(clip_id,'pass_audio',token)
        self._atomic_save(frames.cpu(),frames_path)
        self._atomic_save(portable_tree(audio),audio_path)
        return {'pass':number,'frames':os.path.basename(frames_path),'audio':os.path.basename(audio_path),
                'width':int(frames.shape[2]),'height':int(frames.shape[1])}


    @_locked
    def store_source_media(self, clip_id, frames, audio):
        self._manifest=self._load_manifest()
        meta=self._manifest.get('clips',{}).get(clip_id)
        if meta is None: raise ValueError('Store a take before attaching its source media.')
        token=meta.get('generation')
        self._atomic_save(frames.cpu(),self._clip_artifact_path(clip_id,'source_frames',token))
        self._atomic_save(portable_tree(audio),self._clip_artifact_path(clip_id,'source_audio',token))
        extra={'has_source':True,'source_width':int(frames.shape[2]),'source_height':int(frames.shape[1])}
        meta.update(extra)
        self.save_manifest()
