"""Server-side latent caching, validation chains, and lightweight project serialization."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import time
import zipfile
from typing import Any, Dict, List, Optional, Tuple

import torch

from .config import PROJECT_FORMAT, PROJECT_FORMAT_VERSION

log = logging.getLogger("MiniMaxH3MasterDirector.cache")


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
) -> str:
    """Compute a deterministic hash fingerprint representing a clip's exact generation inputs."""
    h = hashlib.sha256()
    h.update(str(prompt or "").strip().encode("utf-8"))
    h.update(f"|{duration:.3f}|{width}|{height}|{seed}|{model_name}".encode("utf-8"))

    if loras:
        for item in sorted(loras, key=lambda x: x.get("name", "")):
            h.update(f"|lora:{item.get('name')}:{item.get('strength', 1.0):.3f}".encode("utf-8"))

    if ref_signatures:
        for sig in ref_signatures:
            h.update(f"|ref:{sig}".encode("utf-8"))

    if upstream_fingerprint:
        h.update(f"|upstream:{upstream_fingerprint}".encode("utf-8"))

    return h.hexdigest()[:24]


class ProjectCacheManager:
    """Manages disk-cached latents, validation state, and lightweight project archives."""

    def __init__(self, project_id: str = "default", base_dir: Optional[str] = None):
        self.project_id = str(project_id or "default").replace("/", "_").replace("\\", "_")
        root = base_dir or get_cache_root_dir()
        self.project_dir = os.path.join(root, self.project_id)
        os.makedirs(self.project_dir, exist_ok=True)
        self.manifest_path = os.path.join(self.project_dir, "manifest.json")
        self._manifest = self._load_manifest()

    def _load_manifest(self) -> Dict[str, Any]:
        if os.path.isfile(self.manifest_path):
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"project_id": self.project_id, "updated_at": time.time(), "clips": {}}

    def save_manifest(self):
        self._manifest["updated_at"] = time.time()
        tmp_path = self.manifest_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self._manifest, f, indent=2)
        shutil.move(tmp_path, self.manifest_path)

    def get_clip_latent_path(self, clip_id: str) -> str:
        return os.path.join(self.project_dir, f"clip_{clip_id}_latent.pt")

    def get_clip_audio_path(self, clip_id: str) -> str:
        return os.path.join(self.project_dir, f"clip_{clip_id}_audio.pt")

    def get_clip_frames_path(self, clip_id: str) -> str:
        return os.path.join(self.project_dir, f"clip_{clip_id}_frames.pt")

    def is_clip_cached_and_valid(self, clip_id: str, current_fingerprint: str) -> bool:
        """Check if clip has stored latents on disk matching the exact fingerprint."""
        clip_meta = self._manifest.get("clips", {}).get(clip_id)
        if not clip_meta or not clip_meta.get("validated", False):
            return False

        if clip_meta.get("fingerprint") != current_fingerprint:
            return False

        latent_path = self.get_clip_latent_path(clip_id)
        return os.path.isfile(latent_path)

    def store_clip_results(
        self,
        clip_id: str,
        fingerprint: str,
        latent_dict: Dict[str, Any],
        audio_dict: Optional[Dict[str, Any]] = None,
        decoded_frames: Optional[torch.Tensor] = None,
        validated: bool = True,
    ):
        """Save clip latent, audio, and frames to server disk cache."""
        latent_path = self.get_clip_latent_path(clip_id)
        torch.save(latent_dict, latent_path)

        if audio_dict is not None:
            audio_path = self.get_clip_audio_path(clip_id)
            torch.save(audio_dict, audio_path)

        if decoded_frames is not None:
            frames_path = self.get_clip_frames_path(clip_id)
            torch.save(decoded_frames.cpu(), frames_path)

        if "clips" not in self._manifest:
            self._manifest["clips"] = {}

        self._manifest["clips"][clip_id] = {
            "fingerprint": fingerprint,
            "validated": bool(validated),
            "updated_at": time.time(),
            "has_audio": audio_dict is not None,
            "has_frames": decoded_frames is not None,
        }
        self.save_manifest()

    def load_clip_latent(self, clip_id: str) -> Optional[Dict[str, Any]]:
        latent_path = self.get_clip_latent_path(clip_id)
        if os.path.isfile(latent_path):
            return torch.load(latent_path, map_location="cpu")
        return None

    def load_clip_audio(self, clip_id: str) -> Optional[Dict[str, Any]]:
        audio_path = self.get_clip_audio_path(clip_id)
        if os.path.isfile(audio_path):
            return torch.load(audio_path, map_location="cpu")
        return None

    def load_clip_frames(self, clip_id: str) -> Optional[torch.Tensor]:
        frames_path = self.get_clip_frames_path(clip_id)
        if os.path.isfile(frames_path):
            return torch.load(frames_path, map_location="cpu")
        return None

    def invalidate_downstream(self, changed_clip_index: int, all_clip_ids: List[str]):
        """Invalidate the changed clip and all subsequent clips in the timeline."""
        for i in range(changed_clip_index, len(all_clip_ids)):
            cid = all_clip_ids[i]
            if cid in self._manifest.get("clips", {}):
                self._manifest["clips"][cid]["validated"] = False
        self.save_manifest()

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
        manifest_refs = project_data.get("server_cache_manifest", {})

        # Check existing server-side cache files against manifest fingerprints
        for cid, ref_meta in manifest_refs.items():
            latent_path = self.get_clip_latent_path(cid)
            if os.path.isfile(latent_path) and ref_meta.get("validated"):
                if cid not in self._manifest.get("clips", {}):
                    self._manifest.setdefault("clips", {})[cid] = {
                        "fingerprint": ref_meta.get("fingerprint"),
                        "validated": True,
                        "updated_at": time.time(),
                    }
        self.save_manifest()
        return project_data.get("timeline", {})
