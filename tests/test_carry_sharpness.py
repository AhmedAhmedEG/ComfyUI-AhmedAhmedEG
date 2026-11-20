"""Carried-context sharpness guard: stops grain/sharpness ratcheting along a chain."""
import unittest
from tests.mock_torch import setup_mock_torch_if_needed
torch = setup_mock_torch_if_needed()
from core.continuity import guard_carried_sharpness, latent_sharpness, extract_streams_from_av_latent


def av(video):
    return {"samples": (video, torch.ones((1, 4, 20))), "_mmx_visible_end": 40}


class CarrySharpnessGuard(unittest.TestCase):
    def setUp(self):
        g = torch.Generator().manual_seed(3)
        smooth = torch.nn.functional.avg_pool3d(torch.randn((1, 6, 10, 20, 20), generator=g), (1, 5, 5), stride=1, padding=(0, 2, 2))
        self.baseline_clip = av(smooth)
        self.base = latent_sharpness(smooth)
        self.sharp = av(smooth + 0.15 * torch.randn((1, 6, 10, 20, 20), generator=g))   # grain added

    def test_sharper_carry_returns_to_baseline_and_audio_is_untouched(self):
        self.assertGreater(latent_sharpness(extract_streams_from_av_latent(self.sharp)[0]), self.base * 1.05)
        out, amount = guard_carried_sharpness(self.sharp, self.base)
        self.assertGreater(amount, 0)
        tail = extract_streams_from_av_latent(out)[0][:, :, -10:]
        self.assertLessEqual(latent_sharpness(tail), self.base * 1.02 + 1e-3)
        self.assertTrue(torch.equal(extract_streams_from_av_latent(out)[1], torch.ones((1, 4, 20))))
        self.assertEqual(out["_mmx_visible_end"], 40)
        self.assertIsNot(out, self.sharp, 'the delivered latent is not modified in place')

    def test_carry_at_or_below_baseline_is_unchanged(self):
        out, amount = guard_carried_sharpness(self.baseline_clip, self.base)
        self.assertIs(out, self.baseline_clip); self.assertEqual(amount, 0.0)
        self.assertIs(guard_carried_sharpness(self.sharp, None)[0], self.sharp)


if __name__ == '__main__':
    unittest.main()
