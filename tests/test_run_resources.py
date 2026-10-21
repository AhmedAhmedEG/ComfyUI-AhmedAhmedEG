import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from core.run_resources import RunResources, SamplingConfiguration, current_resources, execution_resources, shifted_model


class RunResourceContracts(unittest.TestCase):
    def setUp(self):
        self.shared=SamplingConfiguration()
        replacement=patch('core.run_resources._sampling_configuration',self.shared)
        replacement.start();self.addCleanup(replacement.stop)

    def test_shifted_patcher_reused_only_for_identical_parent_and_shifts(self):
        factory = Mock(side_effect=lambda *args: (object(),))
        native = SimpleNamespace(MiniMaxH3SigmaShift=SimpleNamespace(execute=factory))
        with patch.dict('sys.modules', {'comfy_extras.nodes_minimax_h3': native}):
            owner = RunResources()
            parent = object()
            first = owner.get(parent, 12., 3.)
            self.assertIs(owner.get(parent, 12., 3.), first)
            self.assertIsNot(owner.get(parent, 11., 3.), first)
            self.assertIsNot(owner.get(object(), 12., 3.), first)
            self.assertEqual(factory.call_count, 3)
            for _ in range(10): owner.get(object(), 12., 3.)
            self.assertEqual(len(owner.models), 1)
            owner.clear()
            self.assertFalse(owner.holds(first))

    def test_exception_releases_scope_without_leaking_into_next_execution(self):
        owners = []
        @execution_resources
        def run():
            owners.append(current_resources())
            owners[-1].models['fixture'] = (object(), object())
            raise RuntimeError('sampling interrupted')
        for _ in range(2):
            with self.assertRaisesRegex(RuntimeError, 'sampling interrupted'): run()
            self.assertIsNone(current_resources())
        self.assertIsNot(owners[0], owners[1])
        self.assertTrue(all(not owner.models for owner in owners))

    def test_sampling_remask_wrappers_are_released_before_vae(self):
        release=Mock()
        owner=RunResources();patcher=object()
        with patch.object(owner,'_release_model',release):
            owner.track_transient(patcher);owner.track_transient(patcher)
            self.assertEqual(len(owner.transient_models),1)
            owner.release_transients()
            release.assert_not_called()
            self.assertFalse(owner.transient_models)

    def test_decode_boundary_preserves_owned_model_for_native_residency_management(self):
        factory=Mock(side_effect=lambda *args:(object(),))
        native=SimpleNamespace(MiniMaxH3SigmaShift=SimpleNamespace(execute=factory))
        with patch.dict('sys.modules',{'comfy_extras.nodes_minimax_h3':native}):
            owner=RunResources();parent=object();shifted=owner.get(parent,12.,3.)
            with patch.object(owner,'_release_model') as release:
                owner.offload_sampling_models()
                release.assert_not_called()
                owner.clear()
                release.assert_not_called()
                self.assertIs(RunResources().get(parent,12.,3.),shifted)
                self.assertEqual(factory.call_count,1)

    def test_setting_mutation_and_shift_change_replace_the_single_configuration(self):
        factory=Mock(side_effect=lambda *args:(object(),))
        native=SimpleNamespace(MiniMaxH3SigmaShift=SimpleNamespace(execute=factory))
        parent=SimpleNamespace(model_options={'attention':'first'})
        with patch.dict('sys.modules',{'comfy_extras.nodes_minimax_h3':native}):
            owner=RunResources();first=owner.get(parent,12.,3.);owner.clear()
            parent.model_options['attention']='second'
            second=RunResources().get(parent,12.,3.)
            third=RunResources().get(parent,12.,4.)
        self.assertIsNot(first,second);self.assertIsNot(second,third)
        self.assertIs(self.shared.shifted,third)
        self.assertEqual(factory.call_count,3)

    def test_lora_reuse_switching_and_content_invalidation_share_base_weights(self):
        import torch
        weights=torch.ones(4)
        parent=SimpleNamespace(model=weights,model_options={},patches=[])
        files=[{'path':'adapter','sha256':'a','strength':.7}]
        builder=Mock(side_effect=lambda m,f,c:SimpleNamespace(model=m.model,patches=[f[0]['strength']],model_options={}))
        with patch('core.loras.apply_loras',builder):
            first=RunResources().prepare_loras(parent,files)
            self.assertIs(RunResources().prepare_loras(parent,files),first)
            self.assertEqual(builder.call_count,1)
            second=RunResources().prepare_loras(parent,[{**files[0],'strength':.8}])
            third=RunResources().prepare_loras(parent,[{**files[0],'sha256':'b'}])
            bare=RunResources().prepare_loras(parent,[])
        self.assertEqual(builder.call_count,3)
        for model in (first,second,third,bare):self.assertIs(model.model,weights)
        self.assertIs(self.shared.prepared,parent)
        self.assertIsNone(self.shared.shifted)

    def test_adapter_storage_is_byte_bounded_and_native_free_can_clear_handle(self):
        import torch
        self.shared.lora_limit_bytes=16
        self.shared.lora_states['a']={'weights':torch.ones(3)}
        self.shared.lora_states['b']={'weights':torch.ones(3)}
        self.shared.trim_loras()
        self.assertEqual(list(self.shared.lora_states),['b'])
        self.shared.lora_states['large']={'weights':torch.ones(100)}
        self.shared.trim_loras();self.assertFalse(self.shared.lora_states)
        self.shared.parent=object();self.shared.shifted=object();self.shared.reset()
        self.assertIsNone(self.shared.parent);self.assertIsNone(self.shared.shifted)
