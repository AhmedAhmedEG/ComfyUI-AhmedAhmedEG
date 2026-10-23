"""Reuse SHA states for unchanged tensors without retaining their storage."""
from collections import OrderedDict
import threading
import weakref


class TensorFingerprintCache:
    def __init__(self, limit=256):
        self.limit = limit
        self.entries = OrderedDict()
        self.lock = threading.Lock()

    def feed(self, digest, tensor, mode, write):
        try:
            version = tensor._version
            if not isinstance(version, int):
                raise TypeError('No reliable tensor version')
            identity = (version, tuple(tensor.shape), str(tensor.dtype),
                        str(tensor.device), tuple(tensor.stride()), tensor.storage_offset())
            reference = weakref.ref(tensor)
        except (RuntimeError, AttributeError, TypeError):
            # Inference tensors have no mutation counter: scan them normally.
            write(digest)
            return digest
        key = (id(tensor), identity, mode, digest.copy().digest())
        with self.lock:
            cached = self.entries.get(key)
            if cached is not None and cached[0]() is tensor:
                self.entries.move_to_end(key)
                return cached[1].copy()
        write(digest)
        if tensor._version == version:
            with self.lock:
                # Keep only the current revision's states for this tensor.
                for old in list(self.entries):
                    if old[0] == id(tensor) and old[1] != identity:
                        self.entries.pop(old, None)
                self.entries[key] = (reference, digest.copy())
                while len(self.entries) > self.limit:
                    self.entries.popitem(last=False)
        return digest


tensor_fingerprints = TensorFingerprintCache()
