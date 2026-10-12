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
