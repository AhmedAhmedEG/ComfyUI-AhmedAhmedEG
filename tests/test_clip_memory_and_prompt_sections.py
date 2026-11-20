"""Clip memory windows/notes and the prompt-section parser used by the Structured editor."""
import unittest
from tests.mock_torch import setup_mock_torch_if_needed
torch = setup_mock_torch_if_needed()
from core.prompt_engine import parse_prompt_sections, structured_fields_from_text
from core.visual_memory import (memory_entries, memory_windows, memory_note, inject_memory_note,
                                MEMORY_INSTRUCTION)


class PromptSections(unittest.TestCase):
    def test_plain_text_has_no_sections(self):
        found, fields, preamble = parse_prompt_sections("A woman walks into the rain.")
        self.assertFalse(found)
        self.assertEqual(fields, {})
        self.assertEqual(preamble, "A woman walks into the rain.")

    def test_sections_split_and_aliases(self):
        text = ("subject_definitions:\n<Subject 1> is the woman in <Picture 1>.\n\n"
                "summary: A short scene.\n"
                "detailed_description:\nShe turns.\nThe camera pushes in.\n\n"
                "soundscape:\nRain.\nmusic: N/A")
        found, fields, preamble = parse_prompt_sections(text)
        self.assertTrue(found)
        self.assertEqual(preamble, "")
        self.assertEqual(fields["subject_definitions"], "<Subject 1> is the woman in <Picture 1>.")
        self.assertEqual(fields["summary"], "A short scene.")
        self.assertEqual(fields["detailed_description"], "She turns.\nThe camera pushes in.")
        self.assertEqual(fields["overall_soundscape"], "Rain.")
        self.assertEqual(fields["non_diegetic_music"], "N/A")

    def test_plain_text_becomes_the_main_section(self):
        ref = structured_fields_from_text("She turns.", reference_mode=True)
        self.assertEqual(ref["detailed_description"], "She turns.")
        key = structured_fields_from_text("She turns.", reference_mode=False)
        self.assertEqual(key["integrated_multimodal_description"], "She turns.")
        self.assertEqual(key["imd"], "She turns.")

    def test_text_before_first_heading_is_kept(self):
        fields = structured_fields_from_text("Opening note.\nsummary: S\ndetailed_description: D", True)
        self.assertEqual(fields["detailed_description"], "Opening note.\nD")
        self.assertEqual(fields["summary"], "S")


def _clips():
    return [{"id": "a", "name": "Kitchen"}, {"id": "b", "name": "Hall"}, {"id": "c", "name": "Now"}]


class ClipMemory(unittest.TestCase):
    def frames(self, n=120):
        return (torch.arange(n).float().view(n, 1, 1, 1).repeat(1, 4, 4, 3) % 256).to(torch.uint8)

    def test_whole_clip_window_skips_hidden_overlap_and_aligns(self):
        clip = {"memory": [{"clip_id": "b", "note": "the hall, wide view"}]}
        saved = {"b": self.frames(120)}
        windows = memory_windows(clip, _clips(), 2, saved.get, trim_prefix=lambda cid: 22)
        self.assertEqual(len(windows), 1)
        w = windows[0]
        self.assertEqual((w["frames"].shape[0] - 5) % 17, 0)       # H3's 17k+5 frame grid
        self.assertLessEqual(w["frames"].shape[0], 98)            # 120 frames minus the 22-frame overlap
        self.assertAlmostEqual(float(w["frames"][0, 0, 0, 0]), 22 / 255, places=5)  # starts after the overlap, 0..1 floats
        self.assertEqual(w["note"], "the hall, wide view")

    def test_part_of_a_clip(self):
        clip = {"memory": [{"clip_id": "a", "start": 1.0, "end": 2.0}]}
        w = memory_windows(clip, _clips(), 2, {"a": self.frames(240)}.get)[0]
        self.assertAlmostEqual(w["start"], 1.0)
        self.assertEqual(w["frames"].shape[0], 22)                 # 24 frames aligned down to 22

    def test_rejects_later_clips_missing_takes_and_too_many(self):
        with self.assertRaisesRegex(ValueError, "earlier clips"):
            memory_windows({"memory": [{"clip_id": "c"}]}, _clips(), 1, lambda cid: self.frames())
        with self.assertRaisesRegex(ValueError, "generated first"):
            memory_windows({"memory": [{"clip_id": "a"}]}, _clips(), 2, lambda cid: None)
        with self.assertRaisesRegex(ValueError, "at most"):
            memory_entries({"memory": [{"clip_id": "a"}] * 4})
        with self.assertRaisesRegex(ValueError, "start < end"):
            memory_entries({"memory": [{"clip_id": "a", "start": 3, "end": 2}]})
        self.assertEqual(memory_entries({"memory": [{"clip_id": "a", "enabled": False}]}), [])

    def test_note_numbers_videos_after_existing_ones(self):
        note = memory_note([{"note": "the hall"}, {"name": "Kitchen", "note": ""}], first_video=2)
        self.assertIn("<Video 2> is an earlier moment of this film (the hall).", note)
        self.assertIn("<Video 3> is an earlier moment of this film (Kitchen).", note)
        self.assertTrue(note.endswith(MEMORY_INSTRUCTION))

    def test_note_goes_inside_subject_definitions(self):
        prompt = "subject_definitions:\n<Subject 1> is <Picture 1>.\n\nsummary:\nS"
        out = inject_memory_note(prompt, "NOTE")
        self.assertEqual(out, "subject_definitions:\n<Subject 1> is <Picture 1>.\nNOTE\n\nsummary:\nS")
        self.assertEqual(inject_memory_note("Intro\n[Shot 1] go", "NOTE"), "Intro\nNOTE\n\n[Shot 1] go")
        self.assertEqual(inject_memory_note("Just text", "NOTE"), "NOTE\n\nJust text")
        self.assertEqual(inject_memory_note("Just text", ""), "Just text")

    def test_filmstrip_is_a_jpeg_of_visible_frames(self):
        from core.visual_memory import filmstrip
        data = filmstrip(self.frames(60), trim_prefix=10, count=6, height=32)
        self.assertEqual(data[:2], b"\xff\xd8")
        from PIL import Image
        import io
        strip = Image.open(io.BytesIO(data))
        self.assertEqual(strip.size, (6 * 32, 32))   # 4x4 square frames scaled to 32 px tall

    def test_editor_shows_the_same_instruction(self):
        import pathlib
        js = (pathlib.Path(__file__).resolve().parents[1] / "web" / "js" / "minimax_director.js").read_text(encoding="utf-8")
        self.assertIn(MEMORY_INSTRUCTION, js)


if __name__ == "__main__":
    unittest.main()
