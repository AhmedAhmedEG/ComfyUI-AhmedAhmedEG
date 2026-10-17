"""Version-tolerant ComfyUI cleanup at safe H3 execution boundaries."""
import logging
log=logging.getLogger('MiniMaxH3.memory')

def before_refine(active_model):
    try:
        import comfy.model_management as manager
        if not callable(getattr(manager,'loaded_models',None)) or not callable(getattr(manager,'unload_model_and_clones',None)): return
        protected=[active_model]
        nested=getattr(active_model,'get_nested_additional_models',None)
        if callable(nested): protected.extend(nested() or [])
        protected_ids={getattr(m,'clone_base_uuid',None) for m in protected}-{None}
        for patcher in tuple(manager.loaded_models()):
            if type(getattr(patcher,'model',None)).__name__ not in {'MiniMaxH3VideoVAE','MiniMaxH3AudioVAE','MiniMaxH3TEModel_'}: continue
            if any(patcher is p for p in protected) or getattr(patcher,'clone_base_uuid',None) in protected_ids: continue
            manager.unload_model_and_clones(patcher,unload_additional_models=False)
    except (ImportError,AttributeError): pass
    except Exception as exc: log.debug('Pre-refine offload unavailable: %s',exc)

def between_clips():
    import gc
    gc.collect()
    try:
        import comfy.model_management as manager
        cleanup = getattr(manager, 'cleanup_models_gc', None)
        if callable(cleanup): cleanup()
    except (ImportError, AttributeError):
        pass
    try:
        import comfy.memory_management as memory
        if getattr(memory,'aimdo_enabled',False) is not True: return
    except ImportError: return
    for module,method in [('comfy.model_prefetch','cleanup_prefetch_queues'),
            ('comfy.model_management','reset_cast_buffers'),('comfy_aimdo.model_vbar','vbars_reset_watermark_limits')]:
        try:
            import importlib
            operation=getattr(importlib.import_module(module),method,None)
            if callable(operation): operation()
        except Exception as exc: log.debug('Boundary cleanup %s unavailable: %s',method,exc)


def reclaim_host_memory(required_bytes):
    """Ask native inactive-cache reclamation before considering a RAM allocation.

    Never unload all GPU models into host RAM or evict active execution inputs.
    The caller rechecks capacity or chooses mapped output afterward.
    """
    try:
        import gc
        import inspect
        import psutil
        available = psutil.virtual_memory().available
        target = required_bytes + max(1024**3, min(2*1024**3, required_bytes//10))
        if available >= target: return
        gc.collect()
        import comfy.memory_management as memory
        release = getattr(memory, 'extra_ram_release', None)
        if callable(release) and 'free_active' in inspect.signature(release).parameters:
            release(target, free_active=False)
    except (ImportError, AttributeError, TypeError, ValueError) as exc:
        log.debug('Host pressure cleanup unavailable: %s', exc)


def log_memory_boundary(phase, clip_id, policy):
    """Small retained log samples for diagnosing host RAM separately from VRAM."""
    try:
        from pathlib import Path
        fields = {}
        for line in Path('/proc/self/status').read_text().splitlines():
            key, _, value = line.partition(':')
            if key in ('VmRSS', 'VmHWM', 'VmSwap'):
                fields[key] = round(int(value.split()[0]) / 1024, 1)
        for line in Path('/proc/self/smaps_rollup').read_text().splitlines():
            key, _, value = line.partition(':')
            if key in ('Anonymous', 'Pss_File'):
                fields[key] = round(int(value.split()[0]) / 1024, 1)
        import torch
        if torch.cuda.is_available():
            fields['torch_cuda_allocated'] = round(torch.cuda.memory_allocated() / 1048576, 1)
            fields['torch_cuda_reserved'] = round(torch.cuda.memory_reserved() / 1048576, 1)
        log.info('Memory %s clip=%s output=%s MiB=%s', phase, clip_id, policy, fields)
    except (OSError, ImportError, AttributeError, ValueError):
        pass
