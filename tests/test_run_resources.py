import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from core.run_resources import RunResources, current_resources, execution_resources, shifted_model


class RunResourceContracts(unittest.TestCase):
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
            self.assertEqual(len(owner.models), 4)
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
