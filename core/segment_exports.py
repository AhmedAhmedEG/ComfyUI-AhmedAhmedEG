"""Revision-addressed encoded segments for repeat project exports."""
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path


def encoded_segment_path(manager, clip_id, settings):
    artifacts = [(p.name, p.stat().st_size, p.stat().st_mtime_ns)
                 for p in sorted(Path(manager.project_dir).glob(f'clip_{clip_id}_*.pt'))]
    key = hashlib.sha256(json.dumps([settings, artifacts], sort_keys=True).encode()).hexdigest()
    folder = Path(manager.project_dir) / 'encoded_segments'
    folder.mkdir(exist_ok=True)
    return folder / (key + '.mp4')


def commit_encoded_segment(source, target):
    fd, temporary = tempfile.mkstemp(suffix='.mp4.tmp', dir=target.parent)
    os.close(fd)
    try:
        shutil.copyfile(source, temporary)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
