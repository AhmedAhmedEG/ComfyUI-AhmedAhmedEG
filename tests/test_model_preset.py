"""Model Preset: Base / Lightning LoRA / Fast H3 selection and exact Fast H3 sampling."""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.mock_torch import setup_mock_torch_if_needed
setup_mock_torch_if_needed()

from core.model_preset import FAST_H3_SAMPLING
from core.preflight_cache import model_graph_signature, UnsupportedGraph
from nodes.node_model_preset import MiniMaxH3ModelPreset
from nodes.node_settings import MiniMaxH3DirectorSettings


class ModelPresetNode(unittest.TestCase):
    def setUp(self):
        self.node = MiniMaxH3ModelPreset()
        self.inputs = dict(base_model='base', lightning_model='lightning', fast_model='fast',
                           video_vae='vae_fp16', fast_video_vae='vae_int8')

    def test_each_preset_selects_its_model_vae_and_sampling(self):
        model, vae, sampling = self.node.select('Base', 20, 8, **self.inputs)
        self.assertEqual((model, vae, sampling), ('base', 'vae_fp16', {'preset': 'Base', 'steps': 20}))
        model, vae, sampling = self.node.select('Lightning LoRA', 20, 8, **self.inputs)
        self.assertEqual((model, vae, sampling), ('lightning', 'vae_fp16', {'preset': 'Lightning LoRA', 'steps': 8}))
        model, vae, sampling = self.node.select('Fast H3', 20, 8, **self.inputs)
        self.assertEqual((model, vae), ('fast', 'vae_int8'))
        # The exact values of the reference Fast H3 workflow, independent of the step widgets.
        self.assertEqual(sampling, {'preset': 'Fast H3', 'steps': 8, 'cfg': 1.0, 'sampler': 'euler',
                                    'scheduler': 'simple', 'shift_video': 12.0, 'shift_audio': 3.0})
        self.assertEqual(self.node.select('Fast H3', 99, 99, **self.inputs)[2]['steps'], 8)

    def test_fast_h3_falls_back_to_shared_vae_and_missing_branch_is_explicit(self):
        inputs = {k: v for k, v in self.inputs.items() if k != 'fast_video_vae'}
        self.assertEqual(self.node.select('Fast H3', 20, 8, **inputs)[1], 'vae_fp16')
        with self.assertRaisesRegex(ValueError, 'fast_model'):
            self.node.select('Fast H3', 20, 8, video_vae='vae')

    def test_only_the_selected_branch_is_loaded(self):
        unevaluated = {name: None for name in self.inputs}
        self.assertEqual(self.node.check_lazy_status('Lightning LoRA', 20, 8, **unevaluated), ['lightning_model', 'video_vae'])
        self.assertEqual(self.node.check_lazy_status('Fast H3', 20, 8, **unevaluated), ['fast_model', 'fast_video_vae'])
        self.assertEqual(self.node.check_lazy_status('Base', 20, 8, **{**unevaluated, 'base_model': 'ready', 'video_vae': 'ready'}), [])
        for name in self.inputs:
            self.assertTrue(MiniMaxH3ModelPreset.INPUT_TYPES()['optional'][name][1]['lazy'])


class SettingsApplyPreset(unittest.TestCase):
    def test_fast_h3_overrides_every_sampling_value(self):
        config, = MiniMaxH3DirectorSettings().build_config(steps=20, cfg=3.0, sampler='res_multistep', scheduler='beta',
            shift_video=5.0, shift_audio=1.0, model_preset={'preset': 'Fast H3', **FAST_H3_SAMPLING})
        self.assertEqual({k: config[k] for k in FAST_H3_SAMPLING}, FAST_H3_SAMPLING)
        self.assertEqual(config['model_preset'], 'Fast H3')

    def test_base_and_lightning_only_set_steps(self):
        config, = MiniMaxH3DirectorSettings().build_config(steps=25, sampler='euler', scheduler='beta',
            model_preset={'preset': 'Lightning LoRA', 'steps': 8})
        self.assertEqual((config['steps'], config['sampler'], config['scheduler']), (8, 'euler', 'beta'))
        config, = MiniMaxH3DirectorSettings().build_config(steps=25)
        self.assertNotIn('model_preset', config)


class PreflightFollowsPreset(unittest.TestCase):
    def test_signature_follows_the_selected_branch(self):
        with tempfile.TemporaryDirectory() as folder:
            weights = Path(folder) / 'weights.safetensors'; weights.write_bytes(b'x' * 64)
            paths = SimpleNamespace(get_full_path_or_raise=lambda category, name: str(weights))
            graph = {
                'base': {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'ref2va.safetensors', 'weight_dtype': 'default'}},
                'fast': {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'fasth3.safetensors', 'weight_dtype': 'default'}},
                'backend': {'class_type': 'ModelAttentionBackend', 'inputs': {'model': ['fast', 0], 'backend': 'comfy kitchen attention'}},
                'vsa': {'class_type': 'BlockSparseAttention', 'inputs': {'model': ['backend', 0], 'mode': 'vsa', 'sparsity': 10}},
                'vae16': {'class_type': 'VAELoader', 'inputs': {'vae_name': 'vae_fp16.safetensors'}},
                'vae8': {'class_type': 'VAELoader', 'inputs': {'vae_name': 'vae_int8.safetensors'}},
                'preset': {'class_type': 'MiniMaxH3ModelPreset', 'inputs': {'preset': 'Fast H3', 'base_steps': 20, 'lightning_steps': 8,
                           'base_model': ['base', 0], 'fast_model': ['vsa', 0], 'video_vae': ['vae16', 0], 'fast_video_vae': ['vae8', 0]}},
            }
            with patch.dict(sys.modules, {'folder_paths': paths}):
                fast = model_graph_signature(graph, ['preset', 0])
                self.assertEqual(fast['value']['type'], 'BlockSparseAttention')
                self.assertEqual(model_graph_signature(graph, ['preset', 1])['value']['settings']['vae_name'], 'vae_int8.safetensors')
                graph['preset']['inputs']['preset'] = 'Base'
                base = model_graph_signature(graph, ['preset', 0])
                self.assertNotEqual(base, fast, 'Switching preset changes the saved-clip identity')
                self.assertEqual(model_graph_signature(graph, ['preset', 1])['value']['settings']['vae_name'], 'vae_fp16.safetensors')
                graph['preset']['inputs']['preset'] = 'Lightning LoRA'
                with self.assertRaises(UnsupportedGraph):
                    model_graph_signature(graph, ['preset', 0])


if __name__ == '__main__':
    unittest.main()
