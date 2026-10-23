"""Read native model bookkeeping without loading models or scanning tensors."""
import math
import sys


def _bytes(value):
    if isinstance(value, (int, float)) and math.isfinite(value) and value >= 0:
        return int(value)
    return None


def _read(model, name):
    try:
        return _bytes(getattr(model, name)())
    except Exception:
        # The generation worker may replace or release this entry mid-sample.
        return None


def retained_models(module=None):
    module = module if module is not None else sys.modules.get('comfy.model_management')
    if module is None:
        return {'available': False, 'models': [], 'error': 'Model registry unavailable'}
    rows, seen = [], set()
    try:
        entries = tuple(module.current_loaded_models)
    except Exception:
        return {'available': False, 'models': [], 'error': 'Model registry unavailable'}
    for entry in entries:
        try:
            patcher = entry.model
            if patcher is None:
                continue
            model = patcher.model
            device = str(patcher.load_device)
            identity = (id(model), device)
            if identity in seen:
                continue
            seen.add(identity)
            dynamic = bool(patcher.is_dynamic())
            # model_size() can calculate and cache a state_dict: read its already
            # calculated size instead. Never traverse tensors to fill a gap.
            size = _bytes(getattr(patcher, 'size', None))
            if size == 0:
                size = None
            rows.append({'id': f'{id(model):x}:{device}',
                'name': type(model).__name__, 'device': device, 'dynamic': dynamic,
                'model_bytes': size, 'device_bytes': _read(patcher, 'loaded_size'),
                'host_buffer_bytes': _read(patcher, 'loaded_ram_size') if dynamic else None,
                'pinned_bytes': _read(patcher, 'pinned_memory_size') if dynamic else None})
        except Exception:
            continue
    return {'available': True, 'models': rows,
        'scope': 'native_loaded_model_registry',
        'note': 'Native registry only. Host buffers are tracked weight buffers, not total CPU weights or physical RAM residency. Pinned bytes are a subset. GPU shared RAM cannot be attributed per model.'}
