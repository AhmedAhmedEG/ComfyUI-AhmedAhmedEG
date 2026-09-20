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


def _safetensors_path(path_no_ext: str) -> str:
    candidate = path_no_ext + ".safetensors"
    if os.path.isfile(candidate):
        return candidate
    directory, stem = os.path.split(path_no_ext)
    try:
        for filename in os.listdir(directory or "."):
            if filename.casefold() == f"{stem}.safetensors".casefold():
                return os.path.join(directory, filename)
    except OSError:
        pass
    return candidate


def _refmod_members(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(meta, dict):
        return []
    if meta.get("kind") != "bundle":
        return [meta] if meta.get("kind") in MOD_KINDS else []
    members = meta.get("members")
    if meta.get("_format_version") != 5 or not isinstance(members, list) or not 1 <= len(members) <= 256:
        return []
    return [m for m in members if isinstance(m, dict) and m.get("kind") in MOD_KINDS]


def _refmod_metadata_is_supported(meta: Optional[Dict[str, Any]]) -> bool:
    return isinstance(meta, dict) and bool(_refmod_members(meta))


def find_refmod_path(name: str) -> str:
    """Find absolute path for a named RefMod across configured directories."""
    decoded = unquote(name).strip()
    if not decoded or decoded in {"None", "(none)"} or ".." in decoded:
        raise ValueError(f"Invalid RefMod identifier: {name}")

    parts = decoded.split("/")
    for root in get_refmod_directories():
        root_path = os.path.abspath(root)
        target = _safetensors_path(os.path.join(root_path, *parts))
        try:
            inside_root = os.path.commonpath((root_path, target)) == root_path
        except ValueError:
            inside_root = False
        if inside_root and os.path.isfile(target):
            return os.path.splitext(target)[0]

    raise FileNotFoundError(f"RefMod '{name}' not found in refmod paths.")


def refmod_fingerprint(name: str) -> Tuple[int, int]:
    """Return mtime_ns and file size for cache invalidation."""
    sf_path = _safetensors_path(find_refmod_path(name))
    stat = os.stat(sf_path)
    return stat.st_mtime_ns, stat.st_size


def _validate_refmod_latent(latent: torch.Tensor, meta: Dict[str, Any], label: str) -> None:
    if meta.get("kind") == "audio":
        valid = getattr(latent, "ndim", 0) == 4 and tuple(latent.shape[:3]) == (1, 32, 2) and latent.shape[3] > 0
    else:
        valid = (getattr(latent, "ndim", 0) == 5 and tuple(latent.shape[:2]) == (1, 24) and
                 all(size > 0 for size in latent.shape[2:]) and all(size % 2 == 0 for size in latent.shape[-2:]))
        valid = valid and (meta.get("kind") != "image" or latent.shape[2] == 1)
    if not valid:
        raise ValueError(f"Invalid tensor layout for RefMod {label}: shape {getattr(latent, 'shape', None)}")


def load_refmods(name: str) -> List[Tuple[torch.Tensor, Dict[str, Any]]]:
    """Load all RefMod members (supporting bundles or single latents)."""
    base_path = find_refmod_path(name)
    sf_path = _safetensors_path(base_path)
    meta = read_refmod_metadata(base_path) or {}
    if not _refmod_metadata_is_supported(meta):
        # Fallback to direct safetensors load if metadata is minimal
        tensors = load_file(sf_path, device="cpu")
        if "latent" in tensors:
            return [(tensors["latent"].clone(), meta)]
        raise ValueError(f"RefMod '{name}' has no supported metadata or 'latent' tensor.")

    members = _refmod_members(meta)
    results: List[Tuple[torch.Tensor, Dict[str, Any]]] = []
    with safe_open(sf_path, framework="pt", device="cpu") as handle:
        for idx, member in enumerate(members):
            key = f"ref_{idx}" if meta.get("kind") == "bundle" else "latent"
            if key not in handle.keys():
                if "latent" in handle.keys():
                    key = "latent"
                else:
                    raise ValueError(f"RefMod '{name}' is missing tensor '{key}'.")
            latent = handle.get_tensor(key).clone()
            if meta.get("kind") == "bundle":
                _validate_refmod_latent(latent, member, f"'{name}' member {idx}")
            results.append((latent, member))
    return results


def load_refmod(name: str) -> Tuple[torch.Tensor, Dict[str, Any]]:
    """Load a single RefMod latent tensor and its metadata."""
    refs = load_refmods(name)
    if len(refs) != 1:
        raise ValueError(f"RefMod '{name}' is a bundle with {len(refs)} items; load all members instead.")
    return refs[0]


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
            refs = load_refmods(name)
        except Exception:
            continue

        for latent, meta in refs:
            kind = meta.get("kind", "image")
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
) -> Dict[Any, str]:
    """Map each RefMod slot (and name) to the next available canonical MiniMax tag."""
    counts = {
        "image": existing_image_count,
        "video": existing_video_count,
        "audio": existing_audio_count,
    }
    tag_map: Dict[Any, str] = {}
    for idx, item in enumerate(refmod_items):
        kind = item.get("kind", "image")
        if kind not in counts:
            kind = "image"
        counts[kind] += 1
        label = {"image": "Picture", "video": "Video", "audio": "Audio"}.get(kind, "Picture")
        canonical_tag = f"<{label} {counts[kind]}>"
        slot = item.get("slot", idx + 1)
        tag_map[slot] = canonical_tag
        if "name" in item and item["name"]:
            tag_map[str(item["name"]).strip().lower()] = canonical_tag
    return tag_map


def translate_refmod_aliases(text: str, tag_map: Dict[Any, str]) -> str:
    """Replace all `<RefMod N>` or `<Name>` aliases in prompt text with the resolved canonical tags."""
    if not isinstance(text, str) or not text:
        return text

    def _replace(match: re.Match) -> str:
        slot = int(match.group(1))
        if slot in tag_map:
            return tag_map[slot]
        return match.group(0)

    res = REFMOD_ALIAS_REGEX.sub(_replace, text)

    # Also translate by name alias if present
    for k, v in tag_map.items():
        if isinstance(k, str):
            res = re.sub(rf"<\s*{re.escape(k)}\s*>", v, res, flags=re.IGNORECASE)

    return res


# In-memory cache for RefMod visual items (decoded pixel tensors for CLIP tokenization)
_REFMOD_VISUAL_CACHE: Dict[str, Tuple[int, Any]] = {}


def get_cached_visual_item(name: str, mtime_ns: int) -> Optional[Any]:
    """Retrieve cached visual item if mtime matches."""
    cached = _REFMOD_VISUAL_CACHE.get(name)
    if cached and cached[0] == mtime_ns:
        return cached[1]
    return None


def set_cached_visual_item(name: str, mtime_ns: int, item: Any) -> None:
    """Store visual item in memory cache."""
    _REFMOD_VISUAL_CACHE[name] = (mtime_ns, item)


def clear_refmod_visual_cache() -> None:
    """Clear visual cache."""
    _REFMOD_VISUAL_CACHE.clear()
