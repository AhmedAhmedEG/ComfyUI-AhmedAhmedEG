"""Bounded, restart-persistent file hashes; only metadata and digests are retained."""
from collections import OrderedDict
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import threading


def _stamp(path):
    value = os.stat(path)
    return [value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns]


def _cache_path():
    try:
        import folder_paths
        root = Path(folder_paths.get_user_directory())
    except (ImportError, AttributeError, TypeError):
        root = Path(__file__).resolve().parent.parent / 'output'
    return root / 'minimax_director' / 'file_fingerprints.json'


class FileFingerprintCache:
    def __init__(self, path=None, limit=1024):
        self.path = Path(path) if path is not None else None
        self.limit = limit
        self.entries = OrderedDict()
        self.loaded = False
        self.lock = threading.RLock()

    def _load(self):
        if self.loaded:
            return
        self.loaded = True
        self.path = self.path or _cache_path()
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if data.get('version') != 1 or not isinstance(data.get('files'), dict):
                return
            for key, row in list(data['files'].items())[-self.limit:]:
                if (isinstance(row, dict) and isinstance(row.get('stamp'), list)
                        and len(row['stamp']) == 5 and re.fullmatch(r'[0-9a-f]{64}', str(row.get('sha256', '')))):
                    self.entries[key] = row
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    def _save(self):
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(dir=self.path.parent, suffix='.tmp')
            with os.fdopen(fd, 'w', encoding='utf-8') as out:
                json.dump({'version': 1, 'files': self.entries}, out)
            os.replace(temporary, self.path)
        except OSError:
            pass  # An unwritable cache must not prevent generation.
        finally:
            if temporary and os.path.exists(temporary):
                try: os.unlink(temporary)
                except OSError: pass

    def get(self, path):
        path = os.path.realpath(path)
        key = hashlib.sha256(os.fsencode(path)).hexdigest()
        with self.lock:
            self._load()
            before = _stamp(path)
            row = self.entries.get(key)
            from .stage_progress import cache_event
            if row is not None and row['stamp'] == before:
                cache_event('File fingerprints','hit')
                self.entries.move_to_end(key)
                return {'sha256': row['sha256'], 'size': before[2]}
            # A replacement/write during hashing must never publish a digest
            # under the wrong file identity. Retry once, then fail explicitly.
            for _ in range(2):
                with open(path, 'rb') as source:
                    digest = hashlib.file_digest(source, 'sha256').hexdigest()
                after = _stamp(path)
                if before == after:
                    break
                before = after
            else:
                raise RuntimeError('File changed while calculating its fingerprint: ' + path)
            self.entries[key] = {'stamp': after, 'sha256': digest}
            cache_event('File fingerprints','miss')
            self.entries.move_to_end(key)
            while len(self.entries) > self.limit:
                self.entries.popitem(last=False)
            self._save()
            return {'sha256': digest, 'size': after[2]}


file_fingerprints = FileFingerprintCache()
