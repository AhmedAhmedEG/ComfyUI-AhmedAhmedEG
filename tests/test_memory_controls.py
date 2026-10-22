import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.memory_controls import request_vram_release
from core.memory_lifecycle import between_clips


class MemoryControls(unittest.TestCase):
    def test_release_uses_native_worker_without_deleting_execution_cache(self):
        queue=Mock();queue.get_current_queue.return_value=([],[])
        with patch('core.run_resources._sampling_configuration') as configuration:
            result=request_vram_release(queue)
            configuration.reset.assert_called_once_with()
        queue.set_flag.assert_called_once_with('unload_models',True)
        self.assertTrue(result['ok'])

    def test_busy_queue_keeps_active_configuration_and_does_not_interrupt(self):
        for state in [([object()],[]),([],[object()])]:
            queue=Mock();queue.get_current_queue.return_value=state
            with patch('core.run_resources._sampling_configuration') as configuration:
                with self.assertRaisesRegex(RuntimeError,'queue is idle'):request_vram_release(queue)
                configuration.reset.assert_not_called()
            queue.set_flag.assert_not_called()

    def test_clip_boundary_preserves_native_weight_and_graph_buffers(self):
        cleanup=Mock();reset=Mock();prefetch=Mock();watermark=Mock()
        manager=SimpleNamespace(cleanup_models_gc=cleanup,reset_cast_buffers=reset)
        modules={'comfy':SimpleNamespace(model_management=manager),
            'comfy.model_management':manager,
            'comfy.memory_management':SimpleNamespace(aimdo_enabled=True),
            'comfy.model_prefetch':SimpleNamespace(cleanup_prefetch_queues=prefetch),
            'comfy_aimdo.model_vbar':SimpleNamespace(vbars_reset_watermark_limits=watermark)}
        with patch.dict(sys.modules,modules):between_clips()
        cleanup.assert_called_once_with()
        for operation in (reset,prefetch,watermark):operation.assert_not_called()


if __name__=='__main__':unittest.main()
