"""One reusable sampling configuration plus execution-scoped temporary storage."""
from contextvars import ContextVar
from functools import wraps
from collections import OrderedDict
import os
import shutil
import tempfile
import logging
import threading

_current = ContextVar('mmx_run_resources', default=None)
log = logging.getLogger('MiniMaxH3.memory')


def _configuration(value, seen=None):
    """Track patch settings without copying/hashing model or adapter weights."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    seen = set() if seen is None else seen
    if id(value) in seen: return ('cycle', id(value))
    if isinstance(value, (dict, list, tuple)):
        seen.add(id(value))
        try:
            if isinstance(value, dict):
                return tuple((str(k), _configuration(v, seen)) for k,v in sorted(value.items(), key=lambda p:str(p[0])))
            return tuple(_configuration(v, seen) for v in value)
        finally: seen.remove(id(value))
    # In-place tensor edits invalidate settings; tensors are never copied.
    try: version = getattr(value, '_version', None)
    except RuntimeError: version = None  # inference tensors have no version counter
    return (id(value), version if isinstance(version, int) else None)


def _model_configuration(model):
    return tuple(_configuration(getattr(model, field, None)) for field in (
        'patches_uuid', 'patches', 'object_patches', 'model_options',
        'wrappers', 'callbacks', 'attachments', 'injections', 'hook_patches',
        'current_hooks', 'forced_hooks', 'force_cast_weights'))


def _native_residency():
    """Read native H3 residency; do not allocate or maintain another weight cache."""
    try:
        import comfy.model_management as manager
        bases={}
        for patcher in manager.loaded_models():
            model=getattr(patcher,'model',None)
            if type(model).__name__=='MiniMaxH3':bases[id(model)]=patcher
        return {'h3_bases':len(bases),'loaded_bytes':sum(p.loaded_size() for p in bases.values())}
    except Exception:return None


class SamplingConfiguration:
    """A single patcher handle; all residency remains native ComfyUI's job.

    Native clones share the base's weights. There is no independent weight store
    or list of previously patched models here. Adapter file tensors are CPU-only.
    """
    def __init__(self):
        self.lock = threading.RLock()
        self.parent = self.prepared = self.shifted = None
        self.revision = self.prepared_revision = self.shifts = None
        self.adapters = ()
        self.lora_states = OrderedDict()
        self.lora_limit_bytes = 256 * 1024**2

    def _select(self, model, files):
        from .loras import apply_loras
        revision = _model_configuration(model)
        adapters = tuple((f['path'], f['sha256'], float(f['strength'])) for f in files)
        if self.parent is model and self.revision == revision and self.adapters == adapters:
            return self.prepared
        previous = self.parent
        self.parent = self.prepared = self.shifted = None
        self.shifts = self.prepared_revision = None
        # A genuinely different checkpoint should not remain resident beside the
        # replacement. Switching settings/clones of one base uses native patching.
        if previous is not None and getattr(previous, 'model', previous) is not getattr(model, 'model', model):
            RunResources._release_model(previous)
        try:
            prepared = apply_loras(model, files, self.lora_states) if files else model
        finally:
            self.trim_loras()
        self.parent, self.revision, self.adapters = model, revision, adapters
        self.prepared, self.prepared_revision = prepared, _model_configuration(prepared)
        log.info('Sampling configuration replaced: model/adapters/settings changed; one active configuration')
        return prepared

    def prepare(self, model, files):
        with self.lock: return self._select(model, files)

    def get(self, model, video, audio):
        from comfy_extras.nodes_minimax_h3 import MiniMaxH3SigmaShift
        from .sampling import native_outputs
        with self.lock:
            if model is not self.prepared or _model_configuration(model) != self.prepared_revision:
                self._select(model, ())
            shifts = (float(video), float(audio))
            if self.shifted is not None and self.shifts == shifts:
                log.info('Sampling configuration reused: base_id=%s configuration_id=%s native=%s',
                    id(getattr(self.parent,'model',self.parent)),id(self.shifted),_native_residency())
                return self.shifted
            self.shifted = None
            self.shifted, = native_outputs(MiniMaxH3SigmaShift.execute(model, *shifts))
            self.shifts = shifts
            log.info('Sampling sigma configuration prepared: video=%s audio=%s base_id=%s configuration_id=%s native=%s',
                *shifts,id(getattr(self.parent,'model',self.parent)),id(self.shifted),_native_residency())
            return self.shifted

    def trim_loras(self):
        from .loras import lora_state_bytes
        total = sum(lora_state_bytes(state) for state in self.lora_states.values())
        while self.lora_states and (len(self.lora_states)>8 or total>self.lora_limit_bytes):
            _, state = self.lora_states.popitem(last=False)
            total -= lora_state_bytes(state)

    def reset(self):
        """Forget our handle; native ComfyUI can retain or free shared weights."""
        with self.lock:
            self.parent = self.prepared = self.shifted = None
            self.revision = self.prepared_revision = self.shifts = None
            self.adapters = ()
            self.lora_states.clear()


_sampling_configuration = SamplingConfiguration()


class RunResources:
    def __init__(self):
        from .reference_cache import ReferenceEncodeCache
        self.reference_encodes = ReferenceEncodeCache()
        self.models = OrderedDict()
        self.paths = []
        self.transient_models = []

    def get(self, model, shift_video, shift_audio):
        key = (id(model), float(shift_video), float(shift_audio))
        shifted = _sampling_configuration.get(model, shift_video, shift_audio)
        self.models.clear()
        self.models[key] = (model, shifted)
        return shifted

    def prepare_loras(self, model, files):
        return _sampling_configuration.prepare(model, files)

    def holds(self, model):
        return any(shifted is model for _, shifted in self.models.values())

    def clear(self):
        log.info('Reference VAE reuse: %d hits, %d misses', self.reference_encodes.hits, self.reference_encodes.misses)
        self.reference_encodes.clear()
        self.release_transients()
        # Dropping run-local handles must not override native model caching.
        # One shared configuration handle survives for the next reroll.
        self.models.clear()

    def track_transient(self, model):
        if not self.holds(model) and all(item is not model for item in self.transient_models):
            self.transient_models.append(model)
        return model

    def release_transients(self):
        # Native LoadedModel switches back to a clone's parent on finalization.
        # Unloading "model and clones" here also evicts the reusable base.
        self.transient_models.clear()

    def offload_sampling_models(self):
        """Release temporary wrappers; native VRAM management stages the VAE.

        Retain the active shifted patcher across runs. Unloading every clone here
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
