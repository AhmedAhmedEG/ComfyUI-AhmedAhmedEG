"""Versioned authoring state and portable media project archives."""
from __future__ import annotations
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import uuid
import zipfile
from .media_io import resolve_input_path

SCHEMA_VERSION = 2


def seed_string(value):
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("Seeds must be decimal integer strings or integers, not floating-point values.")
    number = int(value)
    if number < 0 or number >= 1 << 64:
        raise ValueError("Seeds must be in the unsigned 64-bit range.")
    return str(number)


def migrate_timeline(value):
    if not isinstance(value, dict):
        raise ValueError("Timeline must be an object.")
    state = copy.deepcopy(value)
    version = int(state.get("version", 1))
    if version > SCHEMA_VERSION:
        raise ValueError(f"Unsupported timeline schema {version}.")
    state["version"] = SCHEMA_VERSION
    shots = state.setdefault("clips", [])
    if not isinstance(shots, list):
        raise ValueError("Timeline clips must be a list.")
    for shot in shots:
        if not isinstance(shot, dict):
            raise ValueError("Every shot must be an object.")
        if shot.get("seed") is not None:
            shot["seed"] = seed_string(shot["seed"])
        shot.setdefault("selected", True)
    return state


def merge_timeline(current, incoming, policy="overwrite"):
    incoming = migrate_timeline(incoming)
    if policy == "overwrite":
        return incoming
    if policy != "append":
        raise ValueError("Import policy must be append or overwrite.")
    result = migrate_timeline(current)
    remap = {}
    for ref in incoming.get("references", []):
        old = ref["id"]
        ref["id"] = "ref_" + uuid.uuid4().hex
        remap[old] = ref["id"]
        result.setdefault("references", []).append(ref)
    for shot in incoming["clips"]:
        shot["id"] = "clip_" + uuid.uuid4().hex
        shot["validated"] = False
        shot["ref_ids"] = [remap.get(key, key) for key in shot.get("ref_ids", [])]
        # Imported shared references become local to these appended shots.
        shot["ref_ids"] = list(dict.fromkeys([*[remap.get(key, key) for key in incoming.get("shared_ref_ids", [])], *shot["ref_ids"]]))
        result["clips"].append(shot)
    return result


def asset_fields(state):
    """Yield mutable filename owners for all portable project media."""
    for ref in [*state.get("references", []), *state.get("available_refs", [])]:
        if ref.get("filename"):
            yield ref, "filename"
    for owner in [state, *state.get("clips", [])]:
        source = owner.get("source")
        if isinstance(source, str):
            owner["source"] = source = {"filename": source}
        if isinstance(source, dict) and source.get("filename"):
            yield source, "filename"


def missing_assets(state, input_root):
    missing = []
    for owner, key in asset_fields(copy.deepcopy(state)):
        try:
            resolve_input_path(owner[key], input_root)
        except (ValueError, FileNotFoundError):
            missing.append(owner[key])
    return sorted(set(missing))


def write_portable(state, input_root, destination):
    state = migrate_timeline(state)
    files = {}
    for owner, key in asset_fields(state):
        path = resolve_input_path(owner[key], input_root)
        with open(path, "rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        entry = f"assets/{digest}{Path(path).suffix.lower()}"
        files[entry] = path
        owner[key] = entry
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("project.json", json.dumps({"format": "MiniMaxH3Portable", "version": 1, "timeline": state}, ensure_ascii=False))
        for entry, path in files.items():
            archive.write(path, entry)
    return destination


def read_portable(source, input_root, max_bytes=8 * 1024**3):
    with zipfile.ZipFile(source) as archive:
        infos = archive.infolist()
        if len(infos) > 10000 or sum(item.file_size for item in infos) > max_bytes:
            raise ValueError("Project archive exceeds the import size limit.")
        names = set()
        for info in infos:
            name = PurePosixPath(info.filename)
            if (name.is_absolute() or ".." in name.parts or "\\" in info.filename
                    or ":" in info.filename or info.filename in names
                    or (info.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError("Unsafe or duplicate project archive path.")
            names.add(info.filename)
        if "project.json" not in names or archive.getinfo("project.json").file_size > 16 * 1024**2:
            raise ValueError("Archive has no valid project manifest.")
        manifest = json.loads(archive.read("project.json"))
        if manifest.get("format") != "MiniMaxH3Portable" or manifest.get("version") != 1:
            raise ValueError("Unsupported portable project.")
        state = migrate_timeline(manifest["timeline"])
        imports = []
        folder = "minimax_imports/" + uuid.uuid4().hex
        for owner, key in asset_fields(state):
            entry = owner[key]
            if entry not in names or not entry.startswith("assets/"):
                raise ValueError(f"Missing portable asset: {entry}")
            relative = folder + "/" + PurePosixPath(entry).name
            target = Path(input_root) / relative
            imports.append((entry, target))
            owner[key] = relative
        # Validate the entire archive before writing any assets.
        for entry, target in dict(imports).items():
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as stream, open(target, "wb") as output:
                import shutil
                shutil.copyfileobj(stream, output, length=1024 * 1024)
        # Graph references with file provenance become independent uploaded
        # references on another machine; they do not require the old graph.
        references = state.setdefault("references", [])
        ids = {row.get("id") for row in references}
        for row in state.get("available_refs", []):
            if row.get("filename") and row.get("id") not in ids:
                references.append(copy.deepcopy(row)); ids.add(row.get("id"))
        return state


def export_timeline_state(state):
    """Export authoring state without graph-group tensor payloads.

    Groups are rebuilt from connected nodes each execution; their IMAGE/AUDIO
    objects must never enter autosave JSON or the project's UI state output.
    """
    result = dict(state)
    result["clips"] = [{key: value for key, value in shot.items() if key != "group"}
                       for shot in state.get("clips", [])]
    return result


def save_autosave(manager, state):
    state = migrate_timeline(export_timeline_state(state))
    path = Path(manager.project_dir) / "autosave.json"
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return str(path)
