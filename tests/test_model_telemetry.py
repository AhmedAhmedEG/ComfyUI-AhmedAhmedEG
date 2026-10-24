import unittest
import sys
from unittest.mock import patch
from types import SimpleNamespace

from core.model_telemetry import retained_models


class Patcher:
    size = 1000
    load_device = 'cuda:0'

    def __init__(self, model=None):
        self.model = model if model is not None else SimpleNamespace()

    def is_dynamic(self): return True
    def loaded_size(self): return 200
    def loaded_ram_size(self): return 800
    def pinned_memory_size(self): return 600
    def model_size(self): raise AssertionError('Must not calculate tensor sizes')


class ModelTelemetryTests(unittest.TestCase):
    def test_private_rife_cache_reports_metadata_without_loading_or_copying(self):
        tensor=SimpleNamespace(numel=lambda:100,element_size=lambda:2,device='cuda:0')
        host=SimpleNamespace(numel=lambda:20,element_size=lambda:4,device='cpu')
        network=SimpleNamespace(parameters=lambda:iter([tensor,host]),buffers=lambda:iter([tensor]))
        wrapper=SimpleNamespace(model=SimpleNamespace(flownet=network),device='cuda:0')
        owner=SimpleNamespace(MODEL_CACHE={'flownet.pkl_fp16':wrapper,'duplicate':wrapper})
        cls=type('RIFEInterpolation',(),{'__module__':'test_private_vfi'})
        registry=SimpleNamespace(NODE_CLASS_MAPPINGS={'RIFEInterpolation':cls})
        with patch.dict(sys.modules,{'test_private_vfi':owner}):
            rows=retained_models(SimpleNamespace(current_loaded_models=[]),registry)['models']
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['model_bytes'],280)
            self.assertEqual(rows[0]['device_bytes'],200)
            self.assertIn('RIFE',rows[0]['name'])
            self.assertIn('private cache',rows[0]['source'])
            owner.MODEL_CACHE.clear()
            self.assertEqual(retained_models(SimpleNamespace(current_loaded_models=[]),registry)['models'],[])

    def test_shared_base_deduplicated_without_conflating_distinct_models(self):
        first = Patcher()
        clone = Patcher(first.model)
        other = Patcher()
        registry = SimpleNamespace(current_loaded_models=[
            SimpleNamespace(model=m) for m in [first, clone, other, None]])
        sample = retained_models(registry)
        self.assertTrue(sample['available'])
        self.assertEqual(len(sample['models']), 2)
        row = sample['models'][0]
        self.assertEqual((row['model_bytes'], row['device_bytes'],
                          row['host_buffer_bytes'], row['pinned_bytes']), (1000, 200, 800, 600))
        self.assertEqual(row['device'], 'cuda:0')
        self.assertTrue(all(not isinstance(v, Patcher) for r in sample['models'] for v in r.values()))

    def test_standard_loader_does_not_report_zero_host_ram_as_measurement(self):
        model = Patcher()
        model.is_dynamic = lambda: False
        row = retained_models(SimpleNamespace(current_loaded_models=[SimpleNamespace(model=model)]))['models'][0]
        self.assertIsNone(row['host_buffer_bytes'])
        self.assertIsNone(row['pinned_bytes'])

    def test_missing_size_and_racing_getters_are_unknown_not_zero(self):
        model = Patcher()
        model.size = 0
        model.loaded_size = lambda: float('nan')
        def released(): raise KeyError('weights')
        model.loaded_ram_size = released
        row = retained_models(SimpleNamespace(current_loaded_models=[SimpleNamespace(model=model)]))['models'][0]
        self.assertIsNone(row['model_bytes'])
        self.assertIsNone(row['device_bytes'])
        self.assertIsNone(row['host_buffer_bytes'])

    def test_empty_and_unavailable_registry_are_distinct(self):
        self.assertEqual(retained_models(SimpleNamespace(current_loaded_models=[]))['models'], [])
        self.assertFalse(retained_models(SimpleNamespace())['available'])


if __name__ == '__main__': unittest.main()
