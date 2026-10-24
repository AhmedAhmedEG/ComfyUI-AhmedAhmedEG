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


def _rife_models(registry, seen):
    """Read the installed VFI cache; never import, load, move or retain weights."""
    cls=getattr(registry,'NODE_CLASS_MAPPINGS',{}).get('RIFEInterpolation')
    owner=sys.modules.get(getattr(cls,'__module__',''))
    cache=getattr(owner,'MODEL_CACHE',None)
    if not isinstance(cache,dict):return []
    rows=[]
    try:entries=tuple(cache.items())
    except RuntimeError:return []
    for key,wrapper in entries:
        try:
            model=wrapper.model.flownet
            if id(model) in seen:continue
            seen.add(id(model))
            # Parameter metadata only: no state_dict, tensor copies, reads of
            # tensor contents, CUDA synchronization or allocator operations.
            devices={};tensors=set()
            for iterator in (model.parameters(),model.buffers()):
                for tensor in iterator:
                    if id(tensor) in tensors:continue
                    tensors.add(id(tensor))
                    size=int(tensor.numel())*int(tensor.element_size())
                    device=str(tensor.device);devices[device]=devices.get(device,0)+size
            total=sum(devices.values())
            device=str(getattr(wrapper,'device','unknown'))
            gpu=[name for name in devices if name.startswith(('cuda','mps','xpu'))]
            if gpu:device=', '.join(gpu)
            elif devices:device=', '.join(devices)
            rows.append({'id':f'{id(model):x}:vfi','name':f'RIFE · {key}',
                'device':device,'dynamic':False,'source':'ComfyUI-VFI private cache',
                'model_bytes':total,'device_bytes':sum(devices.get(name,0) for name in gpu) if gpu else total,
                'host_buffer_bytes':None,'pinned_bytes':None})
        except (AttributeError,TypeError,RuntimeError,ValueError):continue
    return rows


def retained_models(module=None, node_registry=None):
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
    registry=node_registry if node_registry is not None else sys.modules.get('nodes')
    rows.extend(_rife_models(registry,{identity[0] for identity in seen}))
    return {'available': True, 'models': rows,
        'scope': 'native_and_supported_extension_caches',
        'note': 'Native registry and supported extension caches. Host buffers are tracked weight buffers, not total CPU weights or physical RAM residency. Pinned bytes are a subset. GPU shared RAM cannot be attributed per model.'}
