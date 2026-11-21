"""Fast join test helpers: latent length to keep, full-length noise cut, stored results."""
import os
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tests.mock_torch import setup_mock_torch_if_needed
setup_mock_torch_if_needed()
import torch

from core.join_test import keep_video_tokens, cut_for_join_test, save_result, load_result, JOIN_TEST_FRAMES


class JoinTest(unittest.TestCase):
    def test_keeps_context_plus_about_a_second(self):
        self.assertEqual(keep_video_tokens(0, 1), 1)
        self.assertEqual(keep_video_tokens(39, JOIN_TEST_FRAMES), 1 + -(-(39 + JOIN_TEST_FRAMES - 1) // 8))

    def test_noise_is_full_length_noise_cut_to_the_opening(self):
        if not hasattr(torch, "manual_seed") or getattr(torch, "__mock__", False):
            self.skipTest("needs real torch")
        def prepare_noise(samples, seed, inds=None):
            g = torch.manual_seed(seed)
            return torch.randn(samples.size(), generator=g)
        fake = types.ModuleType("comfy.sample"); fake.prepare_noise = prepare_noise
        package = sys.modules.setdefault("comfy", types.ModuleType("comfy"))
        saved = (getattr(package, "sample", None), sys.modules.get("comfy.sample"))
        package.sample = fake; sys.modules["comfy.sample"] = fake
        def restore():
            package.sample = saved[0]
            if saved[1] is None: sys.modules.pop("comfy.sample", None)
            else: sys.modules["comfy.sample"] = saved[1]
        self.addCleanup(restore)
        latent = {"samples": torch.zeros((1, 4, 20, 2, 2)), "noise_mask": torch.ones((1, 1, 20, 2, 2))}
        short, noise, kept, full = cut_for_join_test(latent, 7, context_frames=39)
        self.assertEqual(full, 20)
        self.assertEqual(short["samples"].shape[2], kept)
        self.assertEqual(short["noise_mask"].shape[2], kept)
        expected = prepare_noise(latent["samples"], 7)[:, :, :kept]
        self.assertTrue(torch.equal(noise, expected))

    def test_results_are_stored_per_clip(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(load_result(folder, "c2"))
            save_result(folder, "c2", {"seed": "1"})
            save_result(folder, "c3", {"seed": "2"})
            save_result(folder, "c2", {"seed": "3"})
            self.assertEqual(load_result(folder, "c2")["seed"], "3")
            self.assertEqual(load_result(folder, "c3")["seed"], "2")
            self.assertIn("time", load_result(folder, "c2"))


if __name__ == "__main__":
    unittest.main()
