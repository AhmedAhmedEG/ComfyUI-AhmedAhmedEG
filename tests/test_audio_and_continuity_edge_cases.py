"""Unit tests for audio post-processing, AV latent unpacking, RefMod tag translation, and prompt engine edge cases."""

import unittest
import sys
import os

pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if pkg_root not in sys.path:
    sys.path.insert(0, pkg_root)

from tests.mock_torch import setup_mock_torch_if_needed
torch = setup_mock_torch_if_needed()

from core.audio_post import concatenate_audio_clips, apply_audio_fade, match_audio_rms
from core.continuity import unpack_av_samples, extract_streams_from_av_latent
from core.refmod import build_refmod_tag_map, translate_refmod_aliases
from core.prompt_engine import build_ref2va_prompt, build_keyframe_mode_prompt


class TestAudioAndContinuityEdgeCases(unittest.TestCase):
    def test_audio_fade_and_concat(self):
        # 1. Test fade on 2 channels
        a1 = torch.ones((1, 2, 48000), dtype=torch.float32)
        faded = apply_audio_fade(a1, sample_rate=48000, fade_in_ms=10.0, fade_out_ms=10.0)
        self.assertEqual(faded.shape, a1.shape)
        self.assertLess(faded[0, 0, 0].item(), 0.1)
        self.assertLess(faded[0, 0, -1].item(), 0.1)

        # 2. Test concatenate_audio_clips
        a2 = torch.full((1, 2, 48000), 2.0, dtype=torch.float32)
        streams = [
            {"waveform": a1, "sample_rate": 48000},
            {"waveform": a2, "sample_rate": 48000},
        ]
        res = concatenate_audio_clips(streams, target_sample_rate=48000, crossfade_ms=20.0)
        self.assertEqual(res["sample_rate"], 48000)
        self.assertEqual(res["waveform"].shape[1], 2)
        self.assertGreater(res["waveform"].shape[2], 48000)

    def test_unpack_av_samples_variations(self):
        # Case A: Dict with tuple (video, audio)
        vid = torch.zeros((1, 16, 10, 32, 32))
        aud = torch.zeros((1, 32, 2, 40))
        d1 = {"samples": (vid, aud)}
        v_out, a_out = extract_streams_from_av_latent(d1)
        self.assertEqual(v_out.shape, vid.shape)
        self.assertEqual(a_out.shape, aud.shape)

        # Case B: Dict with single 5D tensor (synthesize audio)
        d2 = {"samples": vid}
        v_out, a_out = extract_streams_from_av_latent(d2)
        self.assertEqual(v_out.shape, vid.shape)
        self.assertEqual(a_out.shape[:3], (1, 32, 2))

        # Case C: Direct unpack_av_samples
        streams, is_nested = unpack_av_samples((vid, aud))
        self.assertTrue(is_nested)
        self.assertEqual(len(streams), 2)
        self.assertEqual(streams[0].shape, vid.shape)

    def test_refmod_tag_and_alias_translation(self):
        refmod_items = [
            {"id": "mod_1", "slot": 1, "name": "Cyber Samurai", "kind": "image"},
            {"id": "mod_2", "slot": 2, "name": "Synthwave Beat", "kind": "audio"},
        ]
        tag_map = build_refmod_tag_map(refmod_items, existing_image_count=1, existing_video_count=0, existing_audio_count=0)
        self.assertEqual(tag_map[1], "<Picture 2>")
        self.assertEqual(tag_map[2], "<Audio 1>")
        self.assertEqual(tag_map["cyber samurai"], "<Picture 2>")
        self.assertEqual(tag_map["synthwave beat"], "<Audio 1>")

        text = "Starring <Cyber Samurai> with soundtrack by <Synthwave Beat> and extra <RefMod 1>."
        translated = translate_refmod_aliases(text, tag_map)
        self.assertEqual(translated, "Starring <Picture 2> with soundtrack by <Audio 1> and extra <Picture 2>.")

    def test_prompt_engine_modes(self):
        # Test ref2va prompt
        p1 = build_ref2va_prompt(
            subject_definitions="<Picture 1> is hero.",
            summary="A hero emerges.",
            detailed_description="Hero walks down the dark street.",
            soundscape="Rain falling.",
            prompt_mode="structured",
        )
        self.assertIn("subject_definitions:", p1)
        self.assertIn("Hero walks down the dark street.", p1)

        # Test keyframe mode prompt
        p2 = build_keyframe_mode_prompt(
            mode="FL2VA",
            imd="Smooth transition between shots.",
            has_first_frame=True,
            has_last_frame=True,
            duration_sec=5.0,
            prompt_mode="structured",
        )
        self.assertIn("integrated_multimodal_description: Smooth transition between shots.", p2)
        self.assertIn("Picture 1", p2)
        self.assertIn("Picture 2", p2)


if __name__ == "__main__":
    unittest.main()
