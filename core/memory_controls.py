"""Manual release through ComfyUI's queue worker, never the HTTP thread."""


def request_vram_release(queue):
    running, pending = queue.get_current_queue()
    if running or pending:
        raise RuntimeError('Generation is running or queued. Clear VRAM when the queue is idle.')
    # Ask the native worker to unload models AND reset execution-cache handles.
    # Under --highvram a loader can itself hold GPU weights, so unloading the
    # residency list alone is insufficient. Project files and saved results are
    # untouched. The worker owns CUDA synchronization and executor reset.
    from .run_resources import _sampling_configuration
    _sampling_configuration.reset()
    queue.set_flag('free_memory', True)
    return {'ok': True, 'message': 'VRAM release requested. Saved clips and project files are kept.'}
