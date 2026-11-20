"""Chain-anchored contrast: seamless at the join, tied to the chain's first clip, colour untouched."""
import unittest
from tests.mock_torch import setup_mock_torch_if_needed
torch = setup_mock_torch_if_needed()
from core.continuity import anchor_chain_contrast, latent_contrast, extract_streams_from_av_latent

AXES = (0, 2, 3, 4)


def spread(v):
    return float((v - v.mean(dim=AXES, keepdim=True)).std())


class ChainContrast(unittest.TestCase):
    def setUp(self):
        g = torch.Generator().manual_seed(5)
        self.guide = torch.randn((1, 6, 7, 8, 8), generator=g) * 0.9 + 0.2      # previous clip's tail
        self.fresh = torch.randn((1, 6, 25, 8, 8), generator=g) * 0.9 + 0.2      # new content, same look
        self.anchor = latent_contrast(torch.cat([self.guide, self.fresh], dim=2))

    def test_overcontrasted_continuation_matches_join_and_returns_to_chain_start(self):
        biased = torch.cat([self.guide, self.fresh], dim=2) * 1.08                 # H3 render bias at this hop
        latent = {"samples": (biased, torch.ones((1, 4, 30))), "_mmx_visible_end": 60}
        out, seam, end = anchor_chain_contrast(latent, self.guide, self.anchor, 7)
        video, audio = extract_streams_from_av_latent(out)
        self.assertAlmostEqual(seam, 1 / 1.08, places=2, msg='join matches the previous tail')
        self.assertAlmostEqual(spread(video[:, :, 1:7]), spread(self.guide[:, :, 1:7]), delta=0.01)
        self.assertLess(end, 1.0)
        self.assertGreater(end, 1 / 1.08, msg='a 2% deadband is left alone')
        self.assertLess(abs(spread(video[:, :, -3:]) / spread(self.fresh[:, :, -3:]) - 1), 0.03)
        self.assertTrue(torch.allclose(video.mean(dim=AXES), biased.mean(dim=AXES), atol=0.01), 'no colour shift')
        self.assertTrue(torch.equal(audio, torch.ones((1, 4, 30))))
        self.assertEqual(out["_mmx_visible_end"], 60)

    def test_repeated_hops_do_not_drift_either_way(self):
        tail = self.guide
        for hop in range(8):
            g = torch.Generator().manual_seed(100 + hop)
            clip = torch.cat([tail, torch.randn((1, 6, 25, 8, 8), generator=g) * 0.9 + 0.2], dim=2) * 1.06
            out, _, _ = anchor_chain_contrast({"samples": clip}, tail, self.anchor, 7)
            video = out["samples"]
            tail = video[:, :, -7:]
        self.assertLess(abs(latent_contrast(video[:, :, 7:]) / self.anchor - 1), 0.04)

    def test_unchanged_when_nothing_to_do_or_incompatible(self):
        clip = torch.cat([self.guide, self.fresh], dim=2)
        out, seam, end = anchor_chain_contrast({"samples": clip}, self.guide, self.anchor, 7)
        self.assertAlmostEqual(seam, 1.0, places=3)
        self.assertEqual(end, 1.0)
        self.assertTrue(torch.allclose(out["samples"], clip, atol=1e-3))
        same = {"samples": clip}
        self.assertIs(anchor_chain_contrast(same, torch.zeros((1, 3, 7, 8, 8)), self.anchor, 7)[0], same)
        self.assertIs(anchor_chain_contrast(same, None, self.anchor, 7)[0], same)
        self.assertIs(anchor_chain_contrast(same, self.guide, None, 7)[0], same)

    def test_large_scene_change_is_capped(self):
        dark = torch.cat([self.guide, self.fresh * 0.5], dim=2)
        _, _, end = anchor_chain_contrast({"samples": dark}, self.guide, self.anchor, 7)
        self.assertAlmostEqual(end, 1.10, places=3)


if __name__ == '__main__':
    unittest.main()
