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
        end = held[-1, 0, 0]  # colour balance pulled to the anchor, brightness kept
        self.assertAlmostEqual(float(end[0] / end[1]), 0.6 / 0.5, places=4)
        self.assertAlmostEqual(float(end[2] / end[1]), 0.4 / 0.5, places=4)
        self.assertAlmostEqual(float(0.299 * end[0] + 0.587 * end[1] + 0.114 * end[2]), 0.5, places=4)
        tail = undo_hold(held[-4:], hold, 10)
        self.assertTrue(torch.allclose(tail, frames[-4:], atol=1e-5))


    def test_frame_stats_measure_colour_and_spread_for_calibration(self):
        from core.look import frame_stats
        frames = torch.zeros((30, 8, 8, 3))
        frames[:, :, :, 0] = 0.6; frames[:, :, :, 2] = 0.2
        frames[-24:, :4] = 0.0
        start, end = frame_stats(frames), frame_stats(frames, from_end=True)
        self.assertAlmostEqual(start["rgb"][1], 0.0, places=5)
        self.assertGreater(end["std"], start["std"])
        self.assertAlmostEqual(frame_stats(frames * 255)["rgb"][0], start["rgb"][0], places=4)


class BoundaryFrame(unittest.TestCase):
    def frames(self, levels):
        noise = torch.rand((len(levels), 8, 8, 3)) * 0.01
        return torch.tensor(levels).view(-1, 1, 1, 1) + noise

    def test_context_copy_after_the_cut_is_replaced(self):
        from core.continuity import repair_boundary_frame
        # context ... 0.70 0.70 | 0.70 (copy) 0.60 0.60 0.60
        frames = self.frames([0.7, 0.7, 0.7, 0.7, 0.6, 0.6, 0.6])
        out, repaired = repair_boundary_frame(frames.clone(), 3)
        self.assertTrue(repaired)
        self.assertTrue(torch.equal(out[3], out[4]))
        self.assertEqual(out.shape, frames.shape)

    def test_smooth_joins_and_real_cuts_are_left_alone(self):
        from core.continuity import repair_boundary_frame
        smooth = self.frames([0.70, 0.69, 0.68, 0.67, 0.66, 0.65, 0.64])
        self.assertFalse(repair_boundary_frame(smooth.clone(), 3)[1])
        cut_at_join = self.frames([0.7, 0.7, 0.7, 0.3, 0.3, 0.3, 0.3])
        self.assertFalse(repair_boundary_frame(cut_at_join.clone(), 3)[1])
        self.assertFalse(repair_boundary_frame(smooth.clone(), 1)[1])


class HoldUndoForMeasurement(unittest.TestCase):
    def test_hold_gain_is_removed_anywhere_in_the_clip(self):
        from core.look import undo_hold_at
        frames = torch.full((20, 2, 2, 3), 0.5)
        hold = {"start": [1.0, 1.0, 1.0], "end": [0.8, 1.0, 1.2]}
        held = apply_hold(frames, hold)
        self.assertTrue(torch.allclose(undo_hold_at(held[5:9], hold, 20, 5), frames[5:9], atol=1e-5))
        self.assertTrue(torch.allclose(undo_hold_at((held[5:9] * 255), hold, 20, 5), frames[5:9], atol=1e-4))
        self.assertIs(undo_hold_at(frames, None, 20, 0), frames)


class GradedTailJoinFix(unittest.TestCase):
    def test_latent_carry_context_becomes_the_guide_and_is_softened(self):
        from core.continuity import graded_context_guide, latent_sharpness
        torch.manual_seed(0)
        video = torch.randn((1, 4, 8, 6, 6))
        latent, guide, amount = graded_context_guide({"samples": video.clone()}, 3, baseline=latent_sharpness(video) * 0.3)
        self.assertEqual(tuple(guide.shape), (1, 4, 3, 6, 6))
        self.assertGreater(amount, 0)
        self.assertTrue(torch.allclose(latent["samples"][:, :, :3], guide))
        self.assertTrue(torch.equal(latent["samples"][:, :, 3:], video[:, :, 3:]))
        same, guide2, amount2 = graded_context_guide({"samples": video.clone()}, 3, baseline=None)
        self.assertEqual(amount2, 0.0)
        self.assertTrue(torch.equal(guide2, video[:, :, :3]))

    def test_motion_context_guide_blocks_are_collected_in_order(self):
        from core.continuity import graded_guide_keyframes
        blocks = [{"resolved_frame_index": f, "latent": torch.full((1, 4, 1, 2, 2), float(i))} for i, f in enumerate((0, 1, 5))]
        audio = {"resolved_frame_index": 0.0, "audio_latent": torch.zeros(1)}
        later = {"resolved_frame_index": 40, "latent": torch.zeros((1, 4, 1, 2, 2))}
        positive = [[None, {"minimax_keyframes": [blocks[2], blocks[0], audio, blocks[1], later]}]]
        guide, amount = graded_guide_keyframes(positive, span=22, baseline=None)
        self.assertEqual(guide.shape[2], 3)
        self.assertEqual([float(guide[0, 0, k, 0, 0]) for k in range(3)], [0.0, 1.0, 2.0])


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
