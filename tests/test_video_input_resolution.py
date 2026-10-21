"""Source input budgets are independent of output geometry and file contents."""
import unittest
import sys
import types
from unittest.mock import patch
from tests.mock_torch import setup_mock_torch_if_needed
torch = setup_mock_torch_if_needed()
from core.source_media import video_input_dimensions, source_range
from core.project import migrate_timeline


class VideoInputResolution(unittest.TestCase):
    def test_half_megapixel_default_and_small_source_do_not_upscale(self):
        self.assertEqual(video_input_dimensions(1920, 1080), (928, 512))
        self.assertEqual(video_input_dimensions(3840, 2160), (928, 512))
        self.assertEqual(video_input_dimensions(640, 360), (640, 352))

    def test_custom_budgets_are_aligned_and_bounded(self):
        width, height = video_input_dimensions(1920, 1080, {"mode":"short_edge", "short_edge":512})
        self.assertEqual((width, height), (896, 512))
        width, height = video_input_dimensions(1920, 1080, {"mode":"megapixels", "megapixels":.258})
        self.assertEqual(width % 32, 0); self.assertEqual(height % 32, 0)
        self.assertLessEqual(width * height, 258000)
        for bad in ({"mode":"megapixels","megapixels":float('nan')}, {"mode":"short_edge","short_edge":9999}, {"mode":"typo"}):
            with self.assertRaises(ValueError): video_input_dimensions(1920,1080,bad)

    def test_input_budget_does_not_replace_output_canvas_or_original_stream(self):
        frames=torch.zeros((5,128,256,3))
        audio={"waveform":torch.zeros((1,2,10000)),"sample_rate":48000}
        shot={"source":{"filename":"source.mp4"},"source_start":0,"source_end":5/24,
              "video_input_resolution":{"mode":"short_edge","short_edge":64}}
        paths=types.SimpleNamespace(get_input_directory=lambda:'input')
        with patch.dict(sys.modules,{'folder_paths':paths}), \
             patch('core.source_media.load_video',return_value=frames), \
             patch('core.source_media.load_audio',return_value=audio):
            resized=source_range(shot,{},512,288)
            original=source_range(shot,{},512,288,preserve_canvas=True)
        self.assertEqual(resized['model_frames'].shape[1:3],(128,256),'Legacy clip budget must not resize pool-owned inputs')
        self.assertEqual(resized['frames'].shape[1:3],(288,512))
        self.assertEqual(original['frames'].shape,frames.shape)
        self.assertEqual(frames.shape,(5,128,256,3))

    def test_legacy_external_context_is_visible_and_migration_is_idempotent(self):
        old={"clips":[{"id":"next","continuation_source":{"filename":"tail.mp4","end":60}}]}
        migrated=migrate_timeline(old)
        self.assertEqual(len(migrated['clips']),2)
        video,generated=migrated['clips']
        self.assertTrue(video['locked']);self.assertEqual(video['source']['filename'],'tail.mp4')
        self.assertAlmostEqual(video['duration'],56/24)
        self.assertNotIn('continuation_source',generated)
        self.assertEqual(migrate_timeline(migrated),migrated)
        self.assertIn('continuation_source',old['clips'][0])
