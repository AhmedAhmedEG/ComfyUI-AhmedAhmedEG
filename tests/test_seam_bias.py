"""Per-hop seam bias removal: a continued clip is aligned to the moment it re-renders."""
import unittest
from tests.mock_torch import setup_mock_torch_if_needed
torch = setup_mock_torch_if_needed()
from core.continuity import align_to_continued_context, extract_streams_from_av_latent


class SeamBias(unittest.TestCase):
    def test_overcontrasted_rerender_is_aligned_to_its_guide(self):
        g = torch.Generator().manual_seed(5)
        guide = torch.randn((1, 6, 7, 8, 8), generator=g) * 0.9 + 0.2           # previous clip's tail
        fresh = torch.randn((1, 6, 13, 8, 8), generator=g) * 0.9 + 0.2           # new content, same look
        clean = torch.cat([guide, fresh], dim=2)
        biased = clean * 1.06 + 0.08                                             # H3's per-hop render bias
        latent = {"samples": (biased, torch.ones((1, 4, 30))), "_mmx_visible_end": 60}
        out, removed = align_to_continued_context(latent, guide)
        video, audio = extract_streams_from_av_latent(out)
        self.assertAlmostEqual(removed, 1.06, places=2)
        self.assertTrue(torch.allclose(video, clean, atol=1e-3), 'the whole clip loses the bias, content kept')
        self.assertTrue(torch.equal(audio, torch.ones((1, 4, 30))))
        self.assertEqual(out["_mmx_visible_end"], 60)

    def test_unbiased_or_incompatible_input_is_unchanged(self):
        g = torch.Generator().manual_seed(6)
        guide = torch.randn((1, 6, 7, 8, 8), generator=g)
        clip = torch.cat([guide, torch.randn((1, 6, 5, 8, 8), generator=g)], dim=2)
        out, removed = align_to_continued_context({"samples": (clip, torch.zeros((1, 4, 9)))}, guide)
        self.assertAlmostEqual(removed, 1.0, places=4)
        self.assertTrue(torch.allclose(extract_streams_from_av_latent(out)[0], clip, atol=1e-4))
        same = {"samples": (clip, torch.zeros((1, 4, 9)))}
        self.assertIs(align_to_continued_context(same, torch.zeros((1, 3, 7, 8, 8)))[0], same)
        self.assertIs(align_to_continued_context(same, None)[0], same)


if __name__ == '__main__':
    unittest.main()
