"""Content provenance for native loaders and restart-safe project caches."""
import hashlib
import os
from pathlib import Path
from functools import lru_cache


def file_provenance(path):
    stat = os.stat(path)
    return dict(_file_provenance(os.path.realpath(path), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns))


@lru_cache(maxsize=64)
def _file_provenance(path, size, mtime_ns, ctime_ns):
    with open(path, "rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    return {"sha256": digest, "size": size}


def record_provenance(value, path, **options):
    value._mmx_provenance = {"checkpoint": file_provenance(path), "options": options}
    return value


def record_graph_provenance(prompt, unique_id, **values):
    """Track directly connected stock loaders without replacing native nodes.

    Unrecognized upstream nodes keep their live-object cache identity; guessing
    a checkpoint through an arbitrary modifier would permit stale saved takes.
    """
    if not isinstance(prompt, dict):
        return
    current = prompt.get(str(unique_id), {})
    inputs = current.get("inputs", {})
    loaders = {"UNETLoader": ("unet_name", "diffusion_models"),
               "CLIPLoader": ("clip_name", "text_encoders"),
               "VAELoader": ("vae_name", "vae")}
    for socket, value in values.items():
        link = inputs.get(socket)
        if value is None or not isinstance(link, (list, tuple)) or len(link) != 2:
            continue
        upstream = prompt.get(str(link[0]), {})
        kind = upstream.get("class_type")
        if kind not in loaders or link[1] != 0:
            continue
        filename_key, category = loaders[kind]
        settings = upstream.get("inputs", {})
        filename = settings.get(filename_key)
        if not isinstance(filename, str):
            continue
        import folder_paths
        path = folder_paths.get_full_path_or_raise(category, filename)
        options = {key: settings[key] for key in ("weight_dtype", "type", "device") if key in settings}
        if any(not isinstance(option, str) for option in options.values()):
            continue  # linked loader options need live-session identity
        loader_identity = (os.path.realpath(path), tuple(sorted(options.items())))
        # Stock loaders can reuse a live model when a file is overwritten in
        # place. Keep that object's original weight identity until it reloads.
        if getattr(value, "_mmx_provenance_loader", None) == loader_identity:
            continue
        record_provenance(value, path, **options)
        value._mmx_provenance_loader = loader_identity


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
