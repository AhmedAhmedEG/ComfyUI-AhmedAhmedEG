"""Content provenance for native loaders and restart-safe project caches."""
import hashlib
import os
from pathlib import Path


def file_provenance(path):
    with open(path, "rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    return {"sha256": digest, "size": os.path.getsize(path)}


def record_provenance(value, path, **options):
    value._mmx_provenance = {"checkpoint": file_provenance(path), "options": options}
    return value


def runtime_provenance():
    digest = hashlib.sha256()
    root = Path(__file__).resolve().parent.parent
    for folder in (root / "core", root / "nodes"):
        for path in sorted(folder.rglob("*.py")):
            digest.update(str(path.relative_to(root)).replace("\\", "/").encode())
            digest.update(path.read_bytes())
    native = "unavailable"
    try:
        import inspect
        import comfy_extras.nodes_minimax_h3 as h3
        filename = inspect.getsourcefile(h3)
        if filename: native = file_provenance(filename)["sha256"]
    except (TypeError, OSError):
        pass
    return {"director": digest.hexdigest(), "native_h3": native}


def algorithm_provenance(*packs):
    files = {}
    for pack in packs:
        if not isinstance(pack, dict) or not pack.get("enabled", True): continue
        if pack.get("adapter"):
            try:
                from ..nodes.node_semantic_bridge import resolve_semantic_bridge_path
            except ImportError:
                from nodes.node_semantic_bridge import resolve_semantic_bridge_path
            adapter_path = resolve_semantic_bridge_path(pack["adapter"])
            if adapter_path: files[adapter_path] = file_provenance(adapter_path)
        name = pack.get("h3_latent_model") or pack.get("latent_upscale_model")
        if isinstance(name, str) and name and name not in ("interpolate", "interpolation") and not name.startswith("("):
            from .vendor.aimixer.director.h3_latent_upscale import _resolve_model_path
            path = _resolve_model_path(name)
            if path not in files: files[path] = file_provenance(path)
    return sorted(files.values(), key=lambda row: row["sha256"])
