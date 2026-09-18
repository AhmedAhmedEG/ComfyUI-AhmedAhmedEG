"""RefMod safetensors loader and alias translation for MiniMax H3 Master Director."""

from __future__ import annotations

import json
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import unquote

import torch
try:
    from safetensors import safe_open
    from safetensors.torch import load_file
except ImportError:
    safe_open = None
    load_file = None

REFMOD_ALIAS_REGEX = re.compile(r"<\s*refmod\s*_?\s*(\d+)(?:\s*:[^>]+)?\s*>", re.I)
META_KEYS = ("refmod_meta", "audio_refmod_meta")
SKIP_DIRS = {"graph_presets", ".git", "__pycache__"}
MOD_KINDS = {"image", "video", "audio"}


def get_refmod_directories() -> List[str]:
    """Find all configured RefMod directories using ComfyUI folder_paths if available."""
    candidates = []
    try:
        import folder_paths
        try:
            candidates.extend(folder_paths.get_folder_paths("refmods"))
        except Exception:
            pass
        if hasattr(folder_paths, "models_dir"):
            candidates.append(os.path.join(folder_paths.models_dir, "refmods"))
    except ImportError:
        pass

    # Fallback to standard relative path
    candidates.append(os.path.join("models", "refmods"))

    roots: List[str] = []
    seen = set()
    for c in candidates:
        norm = os.path.abspath(os.path.expanduser(c))
        real = os.path.realpath(norm)
        if real not in seen and os.path.isdir(real):
            seen.add(real)
            roots.append(norm)
    return roots


def read_refmod_metadata(path_without_ext: str) -> Optional[Dict[str, Any]]:
    """Read embedded metadata from safetensors header or sidecar JSON."""
    sf_path = path_without_ext + ".safetensors"
    if os.path.isfile(sf_path):
        try:
            with safe_open(sf_path, framework="pt") as handle:
                header = handle.metadata()
            if header:
                for k in META_KEYS:
                    if k in header:
                        return json.loads(header[k])
        except Exception:
            pass

    sidecar = path_without_ext + ".json"
    if os.path.isfile(sidecar):
        try:
            with open(sidecar, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return None


def list_available_refmods() -> List[Dict[str, Any]]:
    """List all available RefMods with metadata for UI dropdowns."""
    results = []
    for root in get_refmod_directories():
        for directory, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for fname in filenames:
                if fname.startswith(".") or not fname.endswith(".safetensors"):
                    continue
                full_path = os.path.join(directory, fname)
                base = full_path[:-len(".safetensors")]
                rel_name = os.path.splitext(os.path.relpath(full_path, root))[0].replace(os.sep, "/")
                meta = read_refmod_metadata(base) or {}
                results.append({
                    "name": rel_name,
                    "kind": meta.get("kind", "image"),
                    "concept": meta.get("concept_type", "generic"),
                    "description": meta.get("description", ""),
                    "path": full_path,
                })
    return sorted(results, key=lambda x: x["name"])


def find_refmod_path(name: str) -> str:
    """Find absolute path for a named RefMod across configured directories."""
    decoded = unquote(name).strip()
    if not decoded or decoded in {"None", "(none)"} or ".." in decoded:
        raise ValueError(f"Invalid RefMod identifier: {name}")

    parts = decoded.split("/")
    for root in get_refmod_directories():
        candidate = os.path.realpath(os.path.join(root, *parts) + ".safetensors")
        if os.path.commonpath((root, candidate)) == os.path.realpath(root) and os.path.isfile(candidate):
            return candidate[:-len(".safetensors")]

    raise FileNotFoundError(f"RefMod '{name}' not found in refmod paths.")


def load_refmod(name: str) -> Tuple[torch.Tensor, Dict[str, Any]]:
    """Load a RefMod latent tensor and its metadata."""
    base_path = find_refmod_path(name)
    meta = read_refmod_metadata(base_path) or {}
    tensors = load_file(base_path + ".safetensors", device="cpu")
    if "latent" not in tensors:
        raise ValueError(f"RefMod '{name}' does not contain a 'latent' tensor.")
    return tensors["latent"].clone(), meta


def process_refmod_rows(
    rows: List[Dict[str, Any]],
    max_slots: int = 8,
) -> List[Dict[str, Any]]:
    """Process user RefMod rows, validating slots and computing scaled latents."""
    if not isinstance(rows, list):
        return []

    loaded: List[Dict[str, Any]] = []
    used_slots = set()

    for row in rows:
        if not isinstance(row, dict) or row.get("enabled", True) is False:
            continue
        try:
            slot = int(row.get("slot", 1))
        except (ValueError, TypeError):
            continue

        if slot < 1 or slot > max_slots or slot in used_slots:
            continue
        used_slots.add(slot)

        name = str(row.get("name", "")).strip()
        if not name:
            continue

        try:
            strength = float(row.get("strength", 1.0))
        except (ValueError, TypeError):
            strength = 1.0
        strength = max(0.0, min(1.0, strength))
        if strength <= 1e-4:
            continue

        try:
            latent, meta = load_refmod(name)
        except Exception as exc:
            continue

        kind = meta.get("kind", "image")
        # Scaled latent: if strength is 1.0, keep full latent; otherwise blend
        scaled_latent = latent * strength

        loaded.append({
            "slot": slot,
            "name": name,
            "kind": kind,
            "strength": strength,
            "description": str(row.get("description", meta.get("description", ""))).strip(),
            "latent": scaled_latent,
            "meta": meta,
        })

    return sorted(loaded, key=lambda x: x["slot"])


def build_refmod_tag_map(
    refmod_items: List[Dict[str, Any]],
    existing_image_count: int,
    existing_video_count: int,
    existing_audio_count: int,
) -> Dict[int, str]:
    """Map each RefMod slot to the next available canonical MiniMax tag."""
    counts = {
        "image": existing_image_count,
        "video": existing_video_count,
        "audio": existing_audio_count,
    }
    tag_map = {}
    for item in refmod_items:
        kind = item["kind"]
        counts[kind] += 1
        label = {"image": "Picture", "video": "Video", "audio": "Audio"}.get(kind, "Picture")
        tag_map[item["slot"]] = f"<{label} {counts[kind]}>"
    return tag_map


def translate_refmod_aliases(text: str, tag_map: Dict[int, str]) -> str:
    """Replace all `<RefMod N>` aliases in prompt text with the resolved canonical tags."""
    if not isinstance(text, str) or not text:
        return text

    def _replace(match: re.Match) -> str:
        slot = int(match.group(1))
        if slot not in tag_map:
            raise ValueError(f"<RefMod {slot}> has no active reference file assigned.")
        return tag_map[slot]

    return REFMOD_ALIAS_REGEX.sub(_replace, text)
