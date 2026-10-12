"""Named server projects. Metadata is separate from disposable tensor caches."""
from __future__ import annotations

import json
import copy
import os
from pathlib import Path
import tempfile
import threading
import time
import uuid

from .cache_manager import get_cache_root_dir, safe_component
from .project import export_timeline_state, migrate_timeline

_LOCK = threading.RLock()
MAX_DOCUMENT_BYTES = 16 * 1024**2


class ProjectConflict(ValueError):
    pass


class ServerProjectStore:
    def __init__(self, root=None):
        self.root = Path(root) if root is not None else Path(get_cache_root_dir()).parent / "minimax_projects"

    def _path(self, project_id):
        return self.root / (safe_component(project_id) + ".json")

    def load(self, project_id):
        path = self._path(project_id)
        with _LOCK:
            if path.stat().st_size > MAX_DOCUMENT_BYTES:
                raise ValueError("Saved project exceeds the metadata size limit.")
            with path.open(encoding="utf-8") as stream:
                document = json.load(stream)
        if document.get("format") != "MiniMaxH3ServerProject" or document.get("version") != 1:
            raise ValueError("Unsupported saved project format.")
        if document.get("project_id") != project_id:
            raise ValueError("Saved project identifier does not match its filename.")
        document["timeline"] = migrate_timeline(document["timeline"])
        document["timeline"].update(project_id=project_id, project_name=document["name"], server_revision=document["revision"])
        return document

    def list(self):
        rows = []
        if not self.root.exists():
            return rows
        for path in self.root.glob("*.json"):
            try:
                document = self.load(path.stem)
                rows.append(self.summary(document))
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                continue  # One damaged document must not hide the rest of the library.
        return sorted(rows, key=lambda item: item["updated_at"], reverse=True)

    @staticmethod
    def summary(document):
        return {key: document[key] for key in ("project_id", "name", "revision", "updated_at")} | {
            "clip_count": len(document["timeline"]["clips"]), "has_workflow": document.get("workflow") is not None}

    def save(self, project_id, name, timeline, workflow, master_node_id, expected_revision=None):
        path = self._path(project_id)
        if not isinstance(name, str):
            raise ValueError("Project name must be text.")
        name = name.strip()
        if not name or len(name) > 128 or any(ord(char) < 32 for char in name):
            raise ValueError("Enter a project name of 1–128 characters without control characters.")
        if not isinstance(workflow, dict) or not isinstance(workflow.get("nodes"), list):
            raise ValueError("Saving a server project requires its ComfyUI workflow.")
        if not any(str(row.get("id")) == str(master_node_id) and row.get("type") in
                   {"MiniMaxH3MasterNode", "MiniMaxH3MasterDirector"} for row in workflow["nodes"] if isinstance(row, dict)):
            raise ValueError("The workflow does not contain this project's Master node.")
        state = migrate_timeline(export_timeline_state(timeline))
        revision = uuid.uuid4().hex
        state.update(project_id=project_id, project_name=name, server_revision=revision)
        workflow = copy.deepcopy(workflow)
        master = next(row for row in workflow["nodes"] if str(row.get("id")) == str(master_node_id))
        builder = state.get("builder_state", {})
        builder = builder if isinstance(builder, str) else json.dumps(builder, ensure_ascii=False)
        serialized = json.dumps(state, ensure_ascii=False, allow_nan=False)
        master.setdefault("widgets_values_named", {}).update(timeline_data=serialized, builder_state=builder)
        generation = {"Next shot":"Next clip", "All shots":"All clips"}.get(state.get("generation_mode"), state.get("generation_mode", "Next clip"))
        master["widgets_values_named"]["generation_mode"] = generation
        master["widgets_values"] = [generation, serialized, builder]
        document = {"format": "MiniMaxH3ServerProject", "version": 1, "project_id": project_id,
                    "name": name, "revision": revision, "updated_at": time.time(),
                    "timeline": state, "workflow": workflow, "master_node_id": master_node_id}
        payload = json.dumps(document, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(payload) > MAX_DOCUMENT_BYTES:
            raise ValueError("Project metadata exceeds 16 MiB. Tensor data belongs in the server cache.")
        with _LOCK:
            if path.exists() and self.load(project_id)["revision"] != expected_revision:
                raise ProjectConflict("This project was saved in another session. Reopen it before saving to avoid overwriting newer work.")
            if not path.exists() and expected_revision:
                raise ProjectConflict("The saved project no longer exists. Start a new project before saving.")
            self.root.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(dir=self.root, suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        return self.summary(document)
