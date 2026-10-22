"""Manual release through ComfyUI's queue worker, never the HTTP thread."""


def request_vram_release(queue):
    running, pending = queue.get_current_queue()
    if running or pending:
        raise RuntimeError('Generation is running or queued. Clear VRAM when the queue is idle.')
    # Keep cached node outputs/loaders: only release the active patcher handles
    # and ask the native worker to unload its GPU models. No project files or
    # generated results are deleted. The worker owns CUDA synchronization.
    from .run_resources import _sampling_configuration
    _sampling_configuration.reset()
    queue.set_flag('unload_models', True)
    return {'ok': True, 'message': 'VRAM release requested. Saved clips and project files are kept.'}
