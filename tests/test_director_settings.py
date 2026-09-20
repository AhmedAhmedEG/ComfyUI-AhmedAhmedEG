"""Unit tests for MiniMaxH3DirectorSettings, MiniMaxH3SamplingSettings, and streamlined Master Director."""

import unittest
from unittest.mock import MagicMock
import sys

import os
pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if pkg_root not in sys.path:
    sys.path.insert(0, pkg_root)

from tests.mock_torch import setup_mock_torch_if_needed
torch = setup_mock_torch_if_needed()

from nodes.node_settings import MiniMaxH3DirectorSettings, MiniMaxH3SamplingSettings
from nodes.node_director import MiniMaxH3MasterDirector


class TestDirectorSettings(unittest.TestCase):
    def setUp(self):
        self.settings_node = MiniMaxH3DirectorSettings()
        self.sampling_node = MiniMaxH3SamplingSettings()
        self.director_node = MiniMaxH3MasterDirector()

    def test_director_settings_defaults(self):
        config, = self.settings_node.build_config()
        self.assertIsInstance(config, dict)
        self.assertEqual(config["width"], 1344)
        self.assertEqual(config["height"], 768)
        self.assertEqual(config["frame_rate"], 24.0)
        self.assertEqual(config["steps"], 25)
        self.assertEqual(config["cfg"], 1.0)
        self.assertEqual(config["sampler"], "res_multistep")
        self.assertEqual(config["scheduler"], "simple")
        self.assertEqual(config["shift_video"], 12.0)
        self.assertEqual(config["shift_audio"], 3.0)
        self.assertEqual(config["seed"], 0)
        self.assertEqual(config["execution_mode"], "All-in-One Generation")
        self.assertEqual(config["prompt_mode"], "structured")
        self.assertEqual(config["run_mode"], "clip_by_clip")
        self.assertEqual(config["continuity_mode"], "Motion Context (Chained)")
        self.assertEqual(config["context_length"], "22")

    def test_sampling_settings_and_chaining(self):
        # Create sampling config
        samp_cfg, = self.sampling_node.build_sampling_config(
            steps=30,
            cfg=1.5,
            sampler="euler",
            scheduler="normal",
            shift_video=15.0,
            shift_audio=4.0,
            seed=42,
        )
        self.assertEqual(samp_cfg["steps"], 30)
        self.assertEqual(samp_cfg["cfg"], 1.5)
        self.assertEqual(samp_cfg["sampler"], "euler")

        # Chain into director settings
        chained, = self.settings_node.build_config(
            width=1920,
            height=1080,
            settings_optional=samp_cfg,
        )
        self.assertEqual(chained["width"], 1920)
        self.assertEqual(chained["height"], 1080)
        self.assertEqual(chained["steps"], 25)  # Overridden by director settings explicit arg

    def test_master_director_execution_with_config(self):
        from unittest.mock import patch
        config, = self.settings_node.build_config(
            width=1280,
            height=720,
            frame_rate=30.0,
            execution_mode="Conditioning Guide Output",
        )

        mock_model = MagicMock()
        mock_vae = MagicMock()
        mock_clip = MagicMock()

        with patch("core.executor.get_native_h3_node") as mock_get_native:
            mock_native = MagicMock()
            mock_positive = [[torch.zeros(1, 768), {"minimax_keyframes": []}]]
            mock_latent = {"samples": (torch.zeros(1, 16, 7, 24, 42), torch.zeros(1, 64, 37))}
            mock_native.execute.return_value = (mock_positive, mock_latent)
            mock_get_native.return_value = mock_native

            result = self.director_node.execute(
                model=mock_model,
                video_vae=mock_vae,
                clip=mock_clip,
                config=config,
                timeline_data="{\"version\":1,\"clips\":[{\"id\":\"c1\",\"name\":\"Shot 1\",\"type\":\"T2V\",\"duration\":3.0,\"prompt\":\"Hero walking\"}]}",
            )

            self.assertIsNotNone(result)
            self.assertEqual(len(result), 9)
            dummy_img, dummy_aud, vid, pos, lat, prompt_out, fps, fc, status = result
            self.assertEqual(fps, 30.0)
            self.assertIn("Emitted conditioning for 1 clip(s)", status)

    def test_master_director_execution_without_config_uses_defaults(self):
        from unittest.mock import patch
        mock_model = MagicMock()
        mock_vae = MagicMock()
        mock_clip = MagicMock()

        with patch("core.executor.get_native_h3_node") as mock_get_native:
            mock_native = MagicMock()
            mock_positive = [[torch.zeros(1, 768), {"minimax_keyframes": []}]]
            mock_latent = {"samples": (torch.zeros(1, 16, 7, 24, 42), torch.zeros(1, 64, 37))}
            mock_native.execute.return_value = (mock_positive, mock_latent)
            mock_get_native.return_value = mock_native

            result = self.director_node.execute(
                model=mock_model,
                video_vae=mock_vae,
                clip=mock_clip,
                execution_mode="Conditioning Guide Output",
                timeline_data="{\"version\":1,\"clips\":[{\"id\":\"c1\",\"name\":\"Shot 1\",\"type\":\"T2V\",\"duration\":5.0,\"prompt\":\"Hero walking\"}]}",
            )

            self.assertIsNotNone(result)
            self.assertEqual(len(result), 9)
            dummy_img, dummy_aud, vid, pos, lat, prompt_out, fps, fc, status = result
            self.assertEqual(fps, 24.0)  # Default 24.0 fps


if __name__ == "__main__":
    unittest.main()
