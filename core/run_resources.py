"""Execution-scoped model wrappers and temporary decoded-frame storage."""
from contextvars import ContextVar
from functools import wraps
from collections import OrderedDict
import os
import shutil
import tempfile
import logging

_current = ContextVar('mmx_run_resources', default=None)
log = logging.getLogger('MiniMaxH3.memory')


class RunResources:
    def __init__(self):
        from .reference_cache import ReferenceEncodeCache
        self.reference_encodes = ReferenceEncodeCache()
        self.models = OrderedDict()
        self.paths = []
        self.transient_models = []

    def get(self, model, shift_video, shift_audio):
        from comfy_extras.nodes_minimax_h3 import MiniMaxH3SigmaShift
        from .sampling import native_outputs
        key = (id(model), float(shift_video), float(shift_audio))
        if key not in self.models:
            shifted, = native_outputs(MiniMaxH3SigmaShift.execute(model, shift_video, shift_audio))
            # Retain the parent too: an id cannot be reused for another model.
            self.models[key] = (model, shifted)
        self.models.move_to_end(key)
        while len(self.models) > 4:
            _, (_, old) = self.models.popitem(last=False)
            self._release_model(old)
        return self.models[key][1]

    def holds(self, model):
        return any(shifted is model for _, shifted in self.models.values())

    def clear(self):
        log.info('Reference VAE reuse: %d hits, %d misses', self.reference_encodes.hits, self.reference_encodes.misses)
        self.reference_encodes.clear()
        self.release_transients()
        for _, shifted in self.models.values():
            self._release_model(shifted)
        self.models.clear()

    def track_transient(self, model):
        if not self.holds(model) and all(item is not model for item in self.transient_models):
            self.transient_models.append(model)
        return model

    def release_transients(self):
        for model in self.transient_models:
            self._release_model(model)
        self.transient_models.clear()

    def offload_sampling_models(self):
        """Release temporary wrappers; native VRAM management stages the VAE.

        Retain owned shifted patchers until run end. Unloading every clone here
        forces complete H3 reloads between clips instead of native partial eviction.
        """
        self.release_transients()

    @staticmethod
    def _release_model(model):
        # Remove managed residency while our patcher is still alive; dropping
        # it first can leave a dead LoadedModel slot retaining shared weights.
        try:
            import comfy.model_management as manager
            release = getattr(manager, 'unload_model_and_clones', None)
            if callable(release): release(model, unload_additional_models=False)
        except Exception as exc:
            log.debug('Owned shifted-model release unavailable: %s', exc)

    def release_spills(self):
        pending = []
        for path in self.paths:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
            except OSError:
                pending.append(path)
        self.paths = pending


def execution_resources(function):
    @wraps(function)
    def call(*args, **kwargs):
        owner = RunResources()
        token = _current.set(owner)
        try:
            return function(*args, **kwargs)
        finally:
            owner.clear()
            owner.release_spills()
            _current.reset(token)
    return call


def current_resources():
    return _current.get()


def shifted_model(model, video, audio):
    owner = current_resources() or RunResources()
    return owner.get(model, video, audio)


def spill_frames(frames, directory):
    """Drop anonymous RGB residency before AudioVAE, preserving exact pixels."""
    import torch
    from .cache_manager import load_frame_tensor
    owner = current_resources()
    if owner is None:
        raise RuntimeError('Decoded frame spilling requires an execution scope.')
    # torch.save preserves backing storage for views, so budget that storage.
    required = frames.untyped_storage().nbytes()
    if shutil.disk_usage(directory).free < required + 1024**3:
        raise RuntimeError('Insufficient cache disk space to stage the decoded clip with 1 GiB headroom.')
    fd, path = tempfile.mkstemp(prefix='decode_', suffix='.pt', dir=directory)
    os.close(fd)
    owner.paths.append(path)
    torch.save(frames.detach().cpu(), path)
    return load_frame_tensor(path)
