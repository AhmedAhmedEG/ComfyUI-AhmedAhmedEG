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


def get_cache_root_dir() -> str:
    """Resolve ComfyUI output cache directory."""
    try:
        import folder_paths
        output_dir = folder_paths.get_output_directory()
    except Exception:
        output_dir = "output"

    cache_dir = os.path.join(output_dir, "minimax_cache")
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

    def load_clip_pre_refine(self, clip_id):
        if not self._manifest.get("clips", {}).get(clip_id, {}).get("has_pre_refine"):
            return None
        return self._load_tensor_file(self._clip_artifact_path(clip_id, "pre_refine"))

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
    def store_clip_results(
        self,
        clip_id: str,
        fingerprint: str,
        latent_dict: Dict[str, Any],
        audio_dict: Optional[Dict[str, Any]] = None,
        decoded_frames: Optional[torch.Tensor] = None,
        validated: bool = True,
        pre_refine_frames=None,
    ):
        """Save clip latent, audio, and frames to server disk cache."""
        self._manifest = self._load_manifest()
        generation = uuid.uuid4().hex
        latent_path = self._clip_artifact_path(clip_id, "latent", generation)
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
            "has_frames": decoded_frames is not None,
            "generation": generation,
            "has_pre_refine": pre_refine_frames is not None,
        }
        self._manifest.setdefault("takes", {})[generation] = {**self._manifest["clips"][clip_id], "clip_id": clip_id}
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

    def load_clip_frames(self, clip_id: str) -> Optional[torch.Tensor]:
        frames_path = self.get_clip_frames_path(clip_id)
        if os.path.isfile(frames_path):
            try:
                return torch.load(frames_path, map_location="cpu", weights_only=True)
            except Exception as exc:
                log.warning("Ignoring unreadable frames cache %s: %s", clip_id, exc)
        return None

    @staticmethod
    def _load_tensor_file(path):
        if not os.path.isfile(path): return None
        return torch.load(path, map_location="cpu", weights_only=True)

    @_locked
    def update_clip_metadata(self, clip_id, metadata):
        clip_id = safe_component(clip_id)
        self._manifest = self._load_manifest()
        if clip_id not in self._manifest["clips"]:
            raise ValueError("Cannot annotate a missing cached shot.")
        self._manifest["clips"][clip_id].update(metadata)
        generation = self._manifest["clips"][clip_id].get("generation")
        if generation in self._manifest.get("takes", {}):
            self._manifest["takes"][generation].update(metadata)
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
