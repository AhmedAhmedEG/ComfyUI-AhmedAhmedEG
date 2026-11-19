"""Preflight follows the native Base / Fast H3 switch layout (no custom selector node)."""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.mock_torch import setup_mock_torch_if_needed
setup_mock_torch_if_needed()

from core.preflight_cache import model_graph_signature


class NativeFastH3Switch(unittest.TestCase):
    def test_native_switch_between_base_and_fast_h3_chains(self):
        # One PrimitiveBoolean drives native MODEL and VAE switches; the Fast H3
        # chain is UNET → ModelSamplingMiniMaxH3 → ModelAttentionBackend → BlockSparseAttention.
        with tempfile.TemporaryDirectory() as folder:
            weights = Path(folder) / 'weights.safetensors'; weights.write_bytes(b'x' * 64)
            paths = SimpleNamespace(get_full_path_or_raise=lambda category, name: str(weights))
            graph = {
                'use_fast': {'class_type': 'PrimitiveBoolean', 'inputs': {'value': True}},
                'base': {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'ref2va.safetensors', 'weight_dtype': 'default'}},
                'base_shift': {'class_type': 'MiniMaxH3SigmaShift', 'inputs': {'model': ['base', 0], 'shift_video': 12.0, 'shift_audio': 3.0}},
                'fast': {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'fasth3.safetensors', 'weight_dtype': 'default'}},
                'fast_shift': {'class_type': 'MiniMaxH3SigmaShift', 'inputs': {'model': ['fast', 0], 'shift_video': 12.0, 'shift_audio': 3.0}},
                'backend': {'class_type': 'ModelAttentionBackend', 'inputs': {'model': ['fast_shift', 0], 'backend': 'comfy kitchen attention'}},
                'vsa': {'class_type': 'BlockSparseAttention', 'inputs': {'model': ['backend', 0], 'mode': 'vsa'}},
                'model_switch': {'class_type': 'ComfySwitchNode', 'inputs': {'switch': ['use_fast', 0], 'on_true': ['vsa', 0], 'on_false': ['base_shift', 0]}},
                'vae16': {'class_type': 'VAELoader', 'inputs': {'vae_name': 'vae_fp16.safetensors'}},
                'vae8': {'class_type': 'VAELoader', 'inputs': {'vae_name': 'vae_int8.safetensors'}},
                'vae_switch': {'class_type': 'ComfySwitchNode', 'inputs': {'switch': ['use_fast', 0], 'on_true': ['vae8', 0], 'on_false': ['vae16', 0]}},
            }
            with patch.dict(sys.modules, {'folder_paths': paths}):
                fast = model_graph_signature(graph, ['model_switch', 0])
                self.assertEqual(fast['model']['type'], 'BlockSparseAttention')
                self.assertEqual(model_graph_signature(graph, ['vae_switch', 0])['model']['settings']['vae_name'], 'vae_int8.safetensors')
                graph['use_fast']['inputs']['value'] = False
                base = model_graph_signature(graph, ['model_switch', 0])
                self.assertEqual(base['model']['type'], 'MiniMaxH3SigmaShift')
                self.assertNotEqual(base, fast, 'Switching model changes the saved-clip identity')
                self.assertEqual(model_graph_signature(graph, ['vae_switch', 0])['model']['settings']['vae_name'], 'vae_fp16.safetensors')


if __name__ == '__main__':
    unittest.main()
