"""Shot-local model LoRAs using ComfyUI's loader; patches never leak to siblings."""
from __future__ import annotations
import hashlib
import math

MAX_CACHED_LORAS = 8


def lora_state_bytes(value):
    """CPU adapter storage only; count aliases once without scanning contents."""
    seen=set()
    def size(item):
        if id(item) in seen:return 0
        seen.add(id(item))
        if isinstance(item,dict):return sum(size(v) for v in item.values())
        if isinstance(item,(list,tuple)):return sum(size(v) for v in item)
        if callable(getattr(item,'numel',None)) and callable(getattr(item,'element_size',None)):
            return item.numel()*item.element_size()
        return 0
    return size(value)


def _patch_count(model):
    patches = getattr(model, "patches", None)
    if isinstance(patches, dict):
        return sum(len(values) for values in patches.values())
    if isinstance(patches, list):
        return len(patches)
    return None


def normalize_loras(rows):
    if rows is None:
        return []
    if not isinstance(rows, list) or len(rows) > 8:
        raise ValueError("A shot supports a list of at most eight LoRAs.")
    result = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("LoRA entries must be objects with a name and strength.")
        if row.get("enabled", row.get("active", True)) is False:
            continue
        name = str(row.get("name", "")).strip()
        strength = float(row.get("strength", 1))
        if not math.isfinite(strength) or not -10 <= strength <= 10:
            raise ValueError("LoRA strength must be finite and between -10 and 10.")
        if name and name.lower() not in ("none", "(none)") and strength != 0:
            result.append({"name": name, "strength": strength})
    return result


def resolve_lora_files(rows):
    rows = normalize_loras(rows)
    if not rows:
        return []
    import folder_paths
    files = []
    for row in rows:
        path = folder_paths.get_full_path_or_raise("loras", row["name"])
        digest = hashlib.sha256()
        with open(path, "rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        files.append({**row, "path": path, "sha256": digest.hexdigest()})
    return files


def apply_loras(model, files, state_cache):
    if not files:
        return model
    import comfy.sd
    import comfy.utils
    patched = model.clone()
    for row in files:
        key = (row["path"], row["sha256"])
        for old in list(state_cache):
            if old[0] == row['path'] and old != key: state_cache.pop(old)
        if key not in state_cache:
            state_cache[key] = comfy.utils.load_torch_file(row["path"], safe_load=True)
        state = state_cache.pop(key)
        state_cache[key] = state
        while len(state_cache) > MAX_CACHED_LORAS:
            state_cache.pop(next(iter(state_cache)))
        before = _patch_count(patched)
        patched, _ = comfy.sd.load_lora_for_models(patched, None, state, row["strength"], 0)
        after = _patch_count(patched)
        if before is not None and after is not None and after <= before:
            raise ValueError(f"LoRA {row['name']!r} has no compatible diffusion-model patches. Select a LoRA compatible with the clip's H3 checkpoint.")
    return patched
