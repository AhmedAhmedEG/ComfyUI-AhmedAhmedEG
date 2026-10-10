"""Video continuation belongs to a timeline clip and survives portable export."""
import math
import unittest
from unittest.mock import patch
from core.source_media import continuation_range
from core.project import asset_fields
from nodes.node_settings import MiniMaxH3DirectorSettings


class ClipVideoContinuation(unittest.TestCase):
    def test_only_tail_of_long_video_is_decoded(self):
        clip = {"continuation_source": {"filename": "input.mp4", "end": 600}}
        with patch("core.source_media.source_range", return_value={"frames": "tail"}) as load:
            self.assertEqual(continuation_range(clip, 960, 544), {"frames": "tail"})
        authored = load.call_args.args[0]
        self.assertAlmostEqual(authored["source_start"], 600 - 56/24)
        self.assertEqual(authored["source_end"], 600)
        self.assertNotIn("duration", authored)

    def test_short_video_and_invalid_end(self):
        with patch("core.source_media.source_range") as load:
            continuation_range({"continuation_source": {"filename": "short.mp4", "end": 1}}, 960, 544)
            self.assertEqual(load.call_args.args[0]["source_start"], 0)
        for end in (0, -1, math.nan, math.inf):
            with self.assertRaises(ValueError):
                continuation_range({"continuation_source": {"filename": "x.mp4", "end": end}}, 960, 544)
        self.assertIsNone(continuation_range({}, 960, 544))

    def test_portable_project_includes_continuation_file(self):
        state = {"clips": [{"continuation_source": {"filename": "tail.mp4", "end": 4}}]}
        self.assertEqual([(row[key]) for row, key in asset_fields(state)], ["tail.mp4"])

    def test_canvas_has_one_config_owner(self):
        config, = MiniMaxH3DirectorSettings().build_config(width=960, height=544,
            canvas_policy="auto", canvas_megapixels=1.5, canvas_aspect="9:16")
        self.assertEqual(config["resolution"], {"mode":"auto", "width":960, "height":544,
            "megapixels":1.5, "aspect":"9:16"})
