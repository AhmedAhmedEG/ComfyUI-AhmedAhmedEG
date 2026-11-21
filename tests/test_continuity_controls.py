"""Continuity controls: look grade, hold-look gain, start-image rules, auto anti-burn."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.mock_torch import setup_mock_torch_if_needed
setup_mock_torch_if_needed()
import torch

from core.look import apply_look, clean_look, hold_target, apply_hold, undo_hold, mean_rgb
from tests import test_runtime_contracts as runtime


class LookMath(unittest.TestCase):
    def test_neutral_look_is_identity_and_validated(self):
        x = torch.rand(2, 4, 4, 3)
        self.assertIs(apply_look(x, None), x)
        self.assertIs(apply_look(x, {"exposure": 0, "contrast": 1}), x)
        with self.assertRaises(ValueError):
            clean_look({"contrast": 3})

    def test_look_moves_brightness_and_colour_the_right_way(self):
        x = torch.full((1, 2, 2, 3), 0.4)
        self.assertGreater(float(apply_look(x, {"exposure": 1}).mean()), 0.7)
        warm = apply_look(x, {"temperature": 1})[0, 0, 0]
        self.assertGreater(float(warm[0]), float(warm[2]))
        grey = apply_look(torch.tensor([[[[0.8, 0.2, 0.2]]]]), {"saturation": 0})[0, 0, 0]
        self.assertAlmostEqual(float(grey[0]), float(grey[1]), places=5)

    def test_hold_gain_ramps_and_undoes_on_the_tail(self):
        frames = torch.full((10, 2, 2, 3), 0.5)
        hold = {"start": [1.0, 1.0, 1.0], "end": hold_target([0.6, 0.5, 0.4], mean_rgb(frames))}
        held = apply_hold(frames, hold)
        self.assertAlmostEqual(float(held[0, 0, 0, 0]), 0.5, places=5)   # seamless join
        self.assertAlmostEqual(float(held[-1, 0, 0, 0]), 0.6, places=4)  # pulled to the anchor
        tail = undo_hold(held[-4:], hold, 10)
        self.assertTrue(torch.allclose(tail, frames[-4:], atol=1e-5))


class ContinuityRules(unittest.TestCase):
    # Borrow the mock pipeline without re-running every RuntimeContracts test.
    setUp = runtime.RuntimeContracts.setUp
    tearDown = runtime.RuntimeContracts.tearDown
    execute = runtime.RuntimeContracts.execute
    native = runtime.RuntimeContracts.native
    strict_sample = runtime.RuntimeContracts.strict_sample

    def test_i2v_without_continuity_needs_exactly_one_image(self):
        with self.assertRaisesRegex(ValueError, "exactly one start image"):
            self.execute([{"id": "one", "type": "I2V", "duration": 1, "continuity_mode": "Independent (No Continuity)"}])

    def test_antiburn_lora_is_added_to_continuing_clips_only(self):
        seen = {}
        def capture(rows):
            seen.setdefault("calls", []).append([dict(r) for r in rows]); return []
        clips = [{"id": "one", "type": "T2VA", "duration": 2, "continuity_mode": "Independent (No Continuity)"},
                 {"id": "two", "type": "T2VA", "duration": 2, "continuity_mode": "Latent Carry (Pinned)", "context_length": 39},
                 {"id": "three", "type": "T2VA", "duration": 2, "continuity_mode": "Latent Carry (Pinned)", "context_length": 39,
                  "antiburn": {"enabled": False}}]
        with patch("nodes.node_director.find_antiburn_lora", return_value="MiniMax H3/h3_antiburn_universal_v1.safetensors"), \
             patch("nodes.node_director.resolve_lora_files", side_effect=capture), \
             patch("core.vendor.aimixer.director.h3_latent_continue.apply_latent_continue", side_effect=lambda latent, **kw: (latent, 39, 0)), \
             patch("core.advanced_sampling.sample_stage", side_effect=lambda model, latent, *a, **kw: latent):
            self.execute(clips)
        self.assertEqual(seen["calls"], [[{"name": "MiniMax H3/h3_antiburn_universal_v1.safetensors", "strength": 0.5, "enabled": True}]])


if __name__ == "__main__":
    unittest.main()
