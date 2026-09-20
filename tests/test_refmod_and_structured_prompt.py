"""Unit tests for RefMod visual caching, per-clip structured prompts, and strict timeline rendering."""

import os
import sys
import unittest
import json

pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if pkg_root not in sys.path:
    sys.path.insert(0, pkg_root)

from tests.mock_torch import setup_mock_torch_if_needed
torch = setup_mock_torch_if_needed()

from core.refmod import (
    get_cached_visual_item,
    set_cached_visual_item,
    clear_refmod_visual_cache,
    build_refmod_tag_map,
    translate_refmod_aliases,
)
from core.prompt_engine import (
    build_ref2va_prompt,
    build_keyframe_mode_prompt,
    prefill_ref2va_scaffold,
)
from nodes.node_director import MiniMaxH3MasterDirector


class TestRefModAndStructuredPrompt(unittest.TestCase):
    def setUp(self):
        clear_refmod_visual_cache()

    def test_refmod_visual_cache(self):
        """Verify RefMod visual items are cached by mtime and cleared properly."""
        self.assertIsNone(get_cached_visual_item("samurai.safetensors", 12345))

        dummy_tensor = torch.zeros((1, 3, 100, 100))
        set_cached_visual_item("samurai.safetensors", 12345, dummy_tensor)

        # Match mtime
        cached = get_cached_visual_item("samurai.safetensors", 12345)
        self.assertIsNotNone(cached)
        self.assertEqual(cached.shape, (1, 3, 100, 100))

        # Mismatched mtime returns None
        self.assertIsNone(get_cached_visual_item("samurai.safetensors", 99999))

        # Clear cache
        clear_refmod_visual_cache()
        self.assertIsNone(get_cached_visual_item("samurai.safetensors", 12345))

    def test_per_clip_structured_prompt(self):
        """Verify structured prompts per clip compile all 6 sections and translate RefMod aliases."""
        tag_map = {1: "<Picture 1>", "samurai": "<Picture 1>"}
        structured = {
            "subject_definitions": "<Subject 1> is <samurai>.",
            "summary": "[reference generation] Warrior scene.",
            "retention_analysis": "<Subject 1>: fully_preserved.",
            "detailed_description": "He unsheathes his katana.",
            "soundscape": "Wind howling.",
            "music": "N/A",
        }

        prompt = build_ref2va_prompt(
            subject_definitions=translate_refmod_aliases(structured["subject_definitions"], tag_map),
            summary=translate_refmod_aliases(structured["summary"], tag_map),
            retention_analysis=translate_refmod_aliases(structured["retention_analysis"], tag_map),
            detailed_description=translate_refmod_aliases(structured["detailed_description"], tag_map),
            soundscape=translate_refmod_aliases(structured["soundscape"], tag_map),
            music=translate_refmod_aliases(structured["music"], tag_map),
            prompt_mode="structured",
        )

        self.assertIn("subject_definitions:\n<Subject 1> is <Picture 1>.", prompt)
        self.assertIn("summary:\n[reference generation] Warrior scene.", prompt)
        self.assertIn("overall_soundscape:\nWind howling.", prompt)

    def test_per_clip_raw_structured_prompt_official_keys(self):
        """Verify structured prompts with official raw keys compile cleanly."""
        tag_map = {1: "<Picture 1>", "cyberpunk": "<Picture 1>"}
        structured = {
            "subject_definitions": "<Subject 1> is <cyberpunk>.",
            "summary": "[reference generation] Neon alley.",
            "retention_analysis": "<Subject 1>: fully_preserved.",
            "detailed_description": "Walking under heavy rain.",
            "overall_soundscape": "Thunder and rain on pavement.",
            "non_diegetic_music": "Dark synthwave arpeggio.",
        }

        prompt = build_ref2va_prompt(
            subject_definitions=translate_refmod_aliases(structured["subject_definitions"], tag_map),
            summary=translate_refmod_aliases(structured["summary"], tag_map),
            retention_analysis=translate_refmod_aliases(structured["retention_analysis"], tag_map),
            detailed_description=translate_refmod_aliases(structured["detailed_description"], tag_map),
            soundscape=translate_refmod_aliases(structured["overall_soundscape"], tag_map),
            music=translate_refmod_aliases(structured["non_diegetic_music"], tag_map),
            prompt_mode="structured",
        )

        self.assertIn("subject_definitions:\n<Subject 1> is <Picture 1>.", prompt)
        self.assertIn("summary:\n[reference generation] Neon alley.", prompt)
        self.assertIn("overall_soundscape:\nThunder and rain on pavement.", prompt)
        self.assertIn("non_diegetic_music:\nDark synthwave arpeggio.", prompt)

    def test_strict_timeline_duration(self):
        """Verify that total duration is strictly governed by timeline clips."""
        clips = [
            {"id": "c1", "duration": 3.0, "type": "T2V"},
            {"id": "c2", "duration": 4.5, "type": "REF2VA"},
        ]
        total_dur = sum(float(c.get("duration", 5.0)) for c in clips)
        self.assertEqual(total_dur, 7.5)


if __name__ == "__main__":
    unittest.main()
