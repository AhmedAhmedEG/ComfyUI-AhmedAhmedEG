"""Pixel-space carry guard: grain/contrast/saturation do not ratchet through carried context."""
import unittest
from tests.mock_torch import setup_mock_torch_if_needed
torch = setup_mock_torch_if_needed()
from core.continuity import guard_carried_look, pixel_look_stats, correct_look_toward, extract_streams_from_av_latent

CYCLE = (1, 4, 4, 4, 4)


class ToyVAE:
    """Latent token k holds the mean of its frames (H3's 1+4+4+4+4 cycle); 3 channels = RGB."""
    def decode(self, latent):
        tokens = [latent[0, :, k].permute(1, 2, 0) for k in range(latent.shape[2])]
        return torch.stack([t for k, t in enumerate(tokens) for _ in range(CYCLE[k % 5])])

    def encode(self, frames):
        out, i, k = [], 0, 0
        while i < frames.shape[0]:
            n = CYCLE[k % 5]; out.append(frames[i:i + n].mean(0).permute(2, 0, 1)); i += n; k += 1
        return torch.stack(out, dim=1).unsqueeze(0)


def grainy(seed, amount, contrast=1.0, tokens=32):
    g = torch.Generator().manual_seed(seed)
    base = 0.45 + 0.1 * torch.linspace(-1, 1, 32).view(1, 1, 32).expand(3, 32, 32)
    video = base.unsqueeze(1).repeat(1, tokens, 1, 1)
    video = video + amount * torch.randn((3, tokens, 32, 32), generator=g)
    video = 0.45 + (video - 0.45) * contrast
    return video.clamp(0, 1).unsqueeze(0)


class CarriedLook(unittest.TestCase):
    def setUp(self):
        self.vae = ToyVAE()
        self.baseline = pixel_look_stats(self.vae.decode(grainy(1, 0.02)))

    def test_grainy_contrasty_tail_is_pulled_back_only_in_the_carried_window(self):
        video = grainy(2, 0.06, contrast=1.15)
        latent = {"samples": (video, torch.ones((1, 4, 9))), "_mmx_visible_end": 99}
        out, report = guard_carried_look(latent, self.baseline, self.vae, self.vae.decode)
        self.assertIn("detail", report)
        new_video, audio = extract_streams_from_av_latent(out)
        start = 32 - 7  # a 22-frame window is 7 tokens, starting on a cycle boundary
        before = pixel_look_stats(self.vae.decode(video[:, :, -7:]))
        after = pixel_look_stats(self.vae.decode(new_video[:, :, -7:]))
        self.assertLess(after["detail"], before["detail"] * 0.9)
        self.assertLess(abs(after["contrast"] / self.baseline["contrast"] - 1), abs(before["contrast"] / self.baseline["contrast"] - 1))
        self.assertTrue(torch.equal(new_video[:, :, :start], video[:, :, :start]), "tokens before the window are untouched")
        self.assertTrue(torch.equal(audio, torch.ones((1, 4, 9))))
        self.assertEqual(out["_mmx_visible_end"], 99)

    def test_matching_tail_or_missing_baseline_is_left_alone(self):
        latent = {"samples": (grainy(1, 0.02), torch.zeros((1, 4, 9)))}
        out, report = guard_carried_look(latent, self.baseline, self.vae, self.vae.decode)
        self.assertEqual(report, {})
        self.assertIs(out, latent)
        self.assertIs(guard_carried_look(latent, None, self.vae, self.vae.decode)[0], latent)

    def test_corrections_are_capped_and_never_sharpen(self):
        flat = self.vae.decode(grainy(3, 0.0, contrast=0.5))
        fixed, report = correct_look_toward(flat, self.baseline)
        self.assertNotIn("detail", report)
        self.assertLessEqual(report.get("contrast", 1.0), 1.10 + 1e-6)
        self.assertGreaterEqual(fixed.min().item(), 0.0)
        self.assertLessEqual(fixed.max().item(), 1.0)

    def test_repeated_hops_do_not_ratchet(self):
        # Each hop the "model" adds grain and contrast to whatever it continues.
        tail = grainy(4, 0.02)
        for hop in range(10):
            g = torch.Generator().manual_seed(50 + hop)
            rendered = (0.45 + (tail - 0.45) * 1.06 + 0.012 * torch.randn(tail.shape, generator=g)).clamp(0, 1)
            out, _ = guard_carried_look({"samples": rendered}, self.baseline, self.vae, self.vae.decode)
            tail = out["samples"]
        final = pixel_look_stats(self.vae.decode(tail[:, :, -7:]))
        self.assertLess(final["detail"], self.baseline["detail"] * 1.35)
        self.assertLess(final["contrast"], self.baseline["contrast"] * 1.20)


if __name__ == '__main__':
    unittest.main()
