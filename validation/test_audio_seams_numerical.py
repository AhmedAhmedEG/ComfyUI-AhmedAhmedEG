"""Continuity audio joins use real overlapping PCM without A/V drift."""
import unittest
import torch
from core.audio_post import prepare_timeline_audio, join_timeline_audio


class TimelineAudioSeams(unittest.TestCase):
    def audio(self, value, length=4800, rate=48000):
        return {'waveform': torch.full((1, 2, length), value), 'sample_rate': rate}

    def test_context_blends_before_cut_without_silence_or_time_loss(self):
        left = self.audio(.25)
        right = self.audio(.5)
        right['seam_prefix'] = self.audio(.5, 960)
        original = left['waveform'].clone()
        parts = prepare_timeline_audio([left, right], 20, False)
        joined = join_timeline_audio([left, right], 20, False)['waveform']
        self.assertEqual(joined.shape[-1], 9600)
        self.assertTrue(torch.equal(joined, torch.cat([p['waveform'] for p in parts], -1)))
        self.assertAlmostEqual(joined[0, 0, 4799].item(), .5)
        self.assertAlmostEqual(joined[0, 0, 4800].item(), .5)
        self.assertGreaterEqual(joined[..., 3840:5760].min().item(), .25)
        self.assertTrue(torch.equal(left['waveform'], original), 'Cached PCM is never edited in place')

    def test_zero_fade_preserves_waveform_and_exact_duration(self):
        clips = [self.audio(.25), self.audio(-.5)]
        clips[1]['seam_prefix'] = self.audio(.7)
        joined = join_timeline_audio(clips, 0, False)['waveform']
        self.assertTrue(torch.equal(joined, torch.cat([c['waveform'] for c in clips], -1)))

    def test_prefix_and_visible_audio_resample_to_same_clock(self):
        left = self.audio(.25)
        right = self.audio(.5, 1600, 16000)
        right['seam_prefix'] = self.audio(.5, 320, 16000)
        joined = join_timeline_audio([left, right], 20, False)['waveform']
        self.assertEqual(joined.shape[-1], 9600)
        self.assertAlmostEqual(joined[0, 0, 4799].item(), joined[0, 0, 4800].item(), places=5)

    def test_no_context_retains_declick_and_gain_matching(self):
        joined = join_timeline_audio([self.audio(.25), self.audio(.5)], 15, True)['waveform']
        self.assertEqual(joined.shape[-1], 9600)
        self.assertEqual(joined[0, 0, 4799].item(), 0)
        self.assertEqual(joined[0, 0, 4800].item(), 0)
        self.assertAlmostEqual(joined[0, 0, 7000].item(), .5 * 10**(-6/20), places=5)


if __name__ == '__main__': unittest.main()
