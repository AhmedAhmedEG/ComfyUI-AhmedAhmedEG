"""Automated test suite for MiniMax H3 Master Director."""

import os
import sys
import unittest
import torch

# Ensure package root is in sys.path
pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if pkg_root not in sys.path:
    sys.path.insert(0, pkg_root)

from core.config import (
    align_frame_count,
    video_latent_t,
    audio_latent_length,
    calculate_dimensions_for_aspect_and_mp,
    CANVAS_MULTIPLE,
)
from core.task_modes import (
    normalize_mode,
    validate_mode_assets,
    MODE_T2VA,
    MODE_FL2VA,
    MODE_REF2VA,
    MODE_INPAINT,
)
from core.prompt_engine import (
    format_alignment_header,
    clean_mentions,
    build_keyframe_mode_prompt,
    build_ref2va_prompt,
    prefill_ref2va_scaffold,
)
from core.refmod import build_refmod_tag_map, translate_refmod_aliases
from core.cache_manager import (
    ProjectCacheManager,
    compute_clip_fingerprint,
)
from core.continuity import (
    match_color_temperature_and_grade,
    trim_continuity_prefix,
)
from core.audio_post import (
    apply_audio_fade,
    concatenate_audio_clips,
)


class TestMiniMaxH3MasterDirector(unittest.TestCase):

    def test_frame_alignment_and_latents(self):
        """Verify 17k + 5 frame snapping and latent temporal dimensions."""
        self.assertEqual(align_frame_count(1), 5)
        self.assertEqual(align_frame_count(5), 5)
        self.assertEqual(align_frame_count(6), 22)
        self.assertEqual(align_frame_count(22), 22)
        self.assertEqual(align_frame_count(23), 39)
        self.assertEqual(align_frame_count(120), 124)  # 17*7 + 5 = 124

        # Video latent t
        self.assertEqual(video_latent_t(5), 2)
        self.assertEqual(video_latent_t(22), 7)  # ((22-5)//17)*5 + 2 = 7
        self.assertEqual(video_latent_t(124), 37)

        # Audio latent t at 40 Hz
        self.assertEqual(audio_latent_length(124), round(124 / 24.0 * 40.0))

    def test_dimension_calculation(self):
        """Verify dimensions are snapped to 32px multiple."""
        w, h = calculate_dimensions_for_aspect_and_mp("16:9", 1.0)
        self.assertEqual(w % CANVAS_MULTIPLE, 0)
        self.assertEqual(h % CANVAS_MULTIPLE, 0)
        self.assertTrue(1300 <= w <= 1400)
        self.assertTrue(700 <= h <= 800)

    def test_task_mode_validation(self):
        """Verify asset limit enforcement across modes."""
        self.assertEqual(normalize_mode("r2v"), MODE_REF2VA)
        self.assertEqual(normalize_mode("fl2v"), MODE_FL2VA)
        self.assertEqual(normalize_mode("inpaint"), MODE_INPAINT)

        # Inpaint requires exactly one image
        valid, errs = validate_mode_assets(MODE_INPAINT, images=[], videos=[], audios=[])
        self.assertFalse(valid)
        valid, errs = validate_mode_assets(MODE_INPAINT, images=[1], videos=[], audios=[])
        self.assertTrue(valid)

        # REF2VA limits (max 9 images, 3 videos, 3 audios)
        valid, errs = validate_mode_assets(MODE_REF2VA, images=[1]*10, videos=[], audios=[])
        self.assertFalse(valid)
        valid, errs = validate_mode_assets(MODE_REF2VA, images=[1]*5, videos=[1]*2, audios=[1]*2)
        self.assertTrue(valid)

    def test_prompt_engine_and_mentions(self):
        """Verify prompt builder formats and alignment line generation."""
        # Mention replacement
        text = "Show @Picture 1 and @Video 2 in the park."
        self.assertEqual(clean_mentions(text), "Show <Picture 1> and <Video 2> in the park.")

        # FL2VA Alignment Header
        header = format_alignment_header("FL2VA", 5.0)
        self.assertIn("Picture 1 (from Shot 1) aligns with the 0.00-second mark", header)
        self.assertIn("Picture 2 (from Shot 1) aligns with", header)

        # Ref2VA 6-section structure
        ref_prompt = build_ref2va_prompt(
            subject_definitions="<Subject 1> is the character.",
            summary="[reference generation] Cinematic scene.",
            retention_analysis="<Subject 1>: fully_preserved",
            detailed_description="[Shot 1] Moving forward.",
            soundscape="Forest wind.",
            music="N/A",
        )
        self.assertIn("subject_definitions:\n<Subject 1> is the character.", ref_prompt)
        self.assertIn("summary:\n[reference generation]", ref_prompt)
        self.assertIn("detailed_description:\n[Shot 1]", ref_prompt)

    def test_refmod_tag_translation(self):
        """Verify RefMod alias replacement."""
        tag_map = {1: "<Picture 2>", 2: "<Audio 1>"}
        orig_text = "Use <RefMod 1> for identity and <RefMod 2> for voice."
        translated = translate_refmod_aliases(orig_text, tag_map)
        self.assertEqual(translated, "Use <Picture 2> for identity and <Audio 1> for voice.")

    def test_lightweight_project_serialization(self):
        """Verify project export is pure metadata without bulky tensors."""
        mgr = ProjectCacheManager("test_project")
        timeline = {
            "clips": [{"id": "c1", "duration": 5.0, "prompt": "test scene"}],
            "items": [],
        }
        exported = mgr.export_lightweight_project_data(timeline, project_name="UnitTest")
        self.assertIn("timeline", exported)
        self.assertIn("server_cache_manifest", exported)
        self.assertEqual(exported["project_name"], "UnitTest")
        # Ensure no tensor or binary data in exported json
        serialized = str(exported)
        self.assertNotIn("tensor", serialized.lower())
        self.assertNotIn("torch", serialized.lower())

    def test_continuity_color_and_trim(self):
        """Verify seam color matching and prefix trimming."""
        frames = torch.ones((25, 64, 64, 3), dtype=torch.float32)
        trimmed = trim_continuity_prefix(frames, context_frames=22)
        self.assertEqual(trimmed.shape[0], 3)

        prev_tail = torch.ones((10, 64, 64, 3), dtype=torch.float32) * 0.8
        graded = match_color_temperature_and_grade(trimmed, prev_tail, blend_window=2)
        self.assertEqual(graded.shape, trimmed.shape)

    def test_audio_post_crossfade(self):
        """Verify audio fading and seamless concatenation."""
        clip1 = {"waveform": torch.ones((2, 48000), dtype=torch.float32) * 0.5, "sample_rate": 48000}
        clip2 = {"waveform": torch.ones((2, 48000), dtype=torch.float32) * 0.5, "sample_rate": 48000}

        faded = apply_audio_fade(clip1["waveform"], 48000, fade_in_ms=10.0, fade_out_ms=10.0)
        self.assertEqual(faded.shape, clip1["waveform"].shape)
        self.assertTrue(faded[0, 0] < 0.1)  # Faded in at start

        merged = concatenate_audio_clips([clip1, clip2], target_sample_rate=48000, crossfade_ms=20.0)
        self.assertIn("waveform", merged)
        self.assertEqual(merged["waveform"].ndim, 3)  # [1, 2, samples]

    def test_image_scaling_modes(self):
        """Verify GPU tensor image scaling modes (Fit, Fill & crop, Fit & pad, Target)."""
        from core.media_io import scale_tensor_image
        img = torch.ones((1, 100, 200, 3), dtype=torch.float32)
        
        # Target stretch
        res_target = scale_tensor_image(img, "Target", 128, 64)
        self.assertEqual(res_target.shape, (1, 64, 128, 3))

        # Fit
        res_fit = scale_tensor_image(img, "Fit", 128, 128)
        self.assertEqual(res_fit.shape[1] % CANVAS_MULTIPLE, 0)
        self.assertEqual(res_fit.shape[2] % CANVAS_MULTIPLE, 0)

        # Fill and crop
        res_fill = scale_tensor_image(img, "Fill and crop", 128, 64)
        self.assertEqual(res_fill.shape, (1, 64, 128, 3))

        # Fit and pad
        res_pad = scale_tensor_image(img, "Fit and pad", 128, 128)
        self.assertEqual(res_pad.shape, (1, 128, 128, 3))

    def test_frame_alignment_modes(self):
        """Verify align_frame_count with up, down, and nearest modes."""
        # 24 is closer to 22 (dist 2) than to 39 (dist 15)
        self.assertEqual(align_frame_count(24, mode="nearest"), 22)
        self.assertEqual(align_frame_count(24, mode="down"), 22)
        self.assertEqual(align_frame_count(24, mode="up"), 39)

        # 38 is closer to 39 (dist 1) than to 22 (dist 16)
        self.assertEqual(align_frame_count(38, mode="nearest"), 39)
        self.assertEqual(align_frame_count(38, mode="down"), 22)
        self.assertEqual(align_frame_count(38, mode="up"), 39)

        # Exact grid matches
        self.assertEqual(align_frame_count(22, mode="nearest"), 22)
        self.assertEqual(align_frame_count(22, mode="down"), 22)
        self.assertEqual(align_frame_count(22, mode="up"), 22)

    def test_advanced_mentions_and_brackets(self):
        """Verify normalization of @mentions and bracketed tags with varying spaces/cases."""
        raw = "Look at @picture1 and @VIDEO 2, also @audio3 and <picture 4>."
        cleaned = clean_mentions(raw)
        self.assertEqual(cleaned, "Look at <Picture 1> and <Video 2>, also <Audio 3> and <Picture 4>.")

    def test_asset_validation_failures(self):
        """Verify ValueError is raised when asset counts or durations violate MiniMax specs."""
        # REF2VA image limit is 9; test with 10
        with self.assertRaises(ValueError):
            validate_mode_assets(MODE_REF2VA, images=[None] * 10, raise_on_error=True)

        # REF2VA video limit is 3; test with 4
        with self.assertRaises(ValueError):
            validate_mode_assets(MODE_REF2VA, videos=[None] * 4, raise_on_error=True)

        # Total reference limit is 12; test with 8 images + 3 videos + 3 audios = 14
        with self.assertRaises(ValueError):
            validate_mode_assets(MODE_REF2VA, images=[None] * 8, videos=[None] * 3, audios=[None] * 3, raise_on_error=True)

        # Exceeding 15s ref duration
        with self.assertRaises(ValueError):
            validate_mode_assets(MODE_REF2VA, ref_video_durations=[16.0], raise_on_error=True)

    def test_silent_and_single_channel_audio(self):
        """Verify audio post-processing handles silent audio (RMS=0) and single channel gracefully."""
        silent = {"waveform": torch.zeros((1, 48000), dtype=torch.float32), "sample_rate": 48000}
        faded = apply_audio_fade(silent["waveform"], 48000)
        self.assertEqual(faded.shape, silent["waveform"].shape)
        self.assertTrue(torch.all(faded == 0))

        merged = concatenate_audio_clips([silent, silent], target_sample_rate=48000)
        self.assertEqual(merged["waveform"].ndim, 3)
        self.assertEqual(merged["waveform"].shape[1], 2)  # Expanded to stereo


if __name__ == "__main__":
    unittest.main()

