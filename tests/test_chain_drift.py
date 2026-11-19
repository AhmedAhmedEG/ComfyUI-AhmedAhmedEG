"""Chain drift correction: continued clips are anchored to their chain's first clip."""
import unittest
from tests.mock_torch import setup_mock_torch_if_needed
torch = setup_mock_torch_if_needed()
from core.continuity import anchor_chain_drift, latent_channel_stats, extract_streams_from_av_latent


def av(video, audio):
    return {"samples": (video, audio), "_mmx_visible_end": 12}


class ChainDrift(unittest.TestCase):
    def setUp(self):
        g = torch.Generator().manual_seed(0)
        self.anchor = av(torch.randn((1, 8, 4, 6, 6), generator=g) * 0.7 + 0.1, torch.zeros((1, 4, 10)))
        # A drifted clip: wider spread (more contrast/saturation) and shifted mean.
        self.drifted = av(torch.randn((1, 8, 4, 6, 6), generator=g) * 1.1 - 0.3, torch.ones((1, 4, 10)))

    def test_full_strength_matches_anchor_statistics(self):
        out = anchor_chain_drift(self.drifted, latent_channel_stats(self.anchor), 1.0)
        mean, std = latent_channel_stats(out); a_mean, a_std = latent_channel_stats(self.anchor)
        self.assertTrue(torch.allclose(mean, a_mean, atol=1e-4)); self.assertTrue(torch.allclose(std, a_std, atol=1e-4))
        self.assertTrue(torch.equal(extract_streams_from_av_latent(out)[1], torch.ones((1, 4, 10))), 'audio is untouched')
        self.assertEqual(out["_mmx_visible_end"], 12)

    def test_strength_scales_the_correction_and_zero_is_a_no_op(self):
        self.assertIs(anchor_chain_drift(self.drifted, latent_channel_stats(self.anchor), 0.0), self.drifted)
        self.assertIs(anchor_chain_drift(self.drifted, None, 1.0), self.drifted)
        half = anchor_chain_drift(self.drifted, latent_channel_stats(self.anchor), 0.5)
        before = latent_channel_stats(self.drifted)[1].mean(); target = latent_channel_stats(self.anchor)[1].mean()
        after = latent_channel_stats(half)[1].mean()
        self.assertAlmostEqual(after.item(), ((before + target) / 2).item(), places=3)


if __name__ == '__main__':
    unittest.main()
