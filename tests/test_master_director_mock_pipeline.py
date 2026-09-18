"""Comprehensive mock-pipeline test suite for MiniMax H3 Master Director.

Validates the full execution flow, multi-segment continuity, conditioning generation,
lightweight project serialization, and modifier nodes WITHOUT downloading any physical models.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch
import torch

pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if pkg_root not in sys.path:
    sys.path.insert(0, pkg_root)

from core.config import FPS, align_frame_count, video_latent_t
from core.task_modes import (
    MODE_FL2VA,
    MODE_REF2VA,
    MODE_I2VA,
    MODE_INPAINT,
    validate_mode_assets,
)
from core.prompt_engine import (
    build_keyframe_mode_prompt,
    build_ref2va_prompt,
    clean_mentions,
    prefill_ref2va_scaffold,
)
from core.refmod import build_refmod_tag_map, translate_refmod_aliases
from core.cache_manager import ProjectCacheManager, compute_clip_fingerprint
from core.continuity import (
    slice_continuity_tail,
    trim_continuity_prefix,
    trim_continuity_audio_prefix,
    match_color_temperature_and_grade,
    repack_av_latent,
)
from core.audio_post import concatenate_audio_clips, apply_audio_fade
from core.selflift import spatial_interpolate_video_latent
from core.face_refine import generate_feathered_ellipse_mask, simple_face_detect_bbox
from nodes.node_director import MiniMaxH3MasterDirector
from nodes.node_selflift import MiniMaxH3DirectorSelfLift
from nodes.node_refine import MiniMaxH3DirectorRefine
from nodes.node_face_refine import MiniMaxH3DirectorFaceRefine
from nodes.node_bridges import MiniMaxH3ReferenceBridge, MiniMaxH3PromptBridge
from nodes.node_tail_extract import MiniMaxH3TailFromLatent


class MockVAE:
    def __init__(self):
        self.audio_sample_rate = 32000

    def decode(self, latent_tensor):
        # Latent tensor [1, C, T, H, W] -> Image batch [T, H*16, W*16, 3]
        if latent_tensor.ndim == 5:
            b, c, t, h, w = latent_tensor.shape
            num_frames = 5 if t <= 2 else ((t - 2) // 5) * 17 + 5
            return torch.zeros((b, num_frames, h * 16, w * 16, 3), dtype=torch.float32)
        elif latent_tensor.ndim == 3 or latent_tensor.ndim == 2:
            # Audio latent decode
            samples = latent_tensor.shape[-1] * 800
            return torch.zeros((1, 2, samples), dtype=torch.float32)
        return torch.zeros((1, 64, 64, 3), dtype=torch.float32)

    def encode(self, image_tensor):
        b, h, w, c = image_tensor.shape
        return torch.zeros((b, 16, 2, h // 16, w // 16), dtype=torch.float32)


class MockCLIP:
    def tokenize(self, text, **kwargs):
        return {"text_tokens": [1, 2, 3]}

    def encode_from_tokens_scheduled(self, tokens):
        return [[torch.zeros(1, 768), {"minimax_payload": MagicMock()}]]


class MockModel:
    def __init__(self):
        self.model_options = {}

    def clone(self):
        m = MockModel()
        m.model_options = dict(self.model_options)
        return m


class TestMockPipeline(unittest.TestCase):

    def setUp(self):
        self.mock_vae = MockVAE()
        self.mock_audio_vae = MockVAE()
        self.mock_clip = MockCLIP()
        self.mock_model = MockModel()

    def test_mock_node_guide_mode_execution(self):
        """Test Master Director execution in 'Conditioning Guide Output' mode."""
        node = MiniMaxH3MasterDirector()

        # Mock the executor's native H3 node calls
        with patch.object(
            node,
            "check_lazy_status",
            return_value=[],
        ):
            with patch("core.executor.get_native_h3_node") as mock_get_native:
                mock_native = MagicMock()
                # Returns (positive, latent)
                mock_positive = [[torch.zeros(1, 768), {"minimax_keyframes": []}]]
                mock_latent = {"samples": (torch.zeros(1, 16, 7, 24, 42), torch.zeros(1, 64, 37))}
                mock_native.execute.return_value = (mock_positive, mock_latent)
                mock_get_native.return_value = mock_native

                result = node.execute(
                    model=self.mock_model,
                    video_vae=self.mock_vae,
                    audio_vae=self.mock_audio_vae,
                    clip=self.mock_clip,
                    mode="FL2VA",
                    execution_mode="Conditioning Guide Output",
                    width=1344,
                    height=768,
                    duration=5.0,
                    frame_rate=24.0,
                    prompt="A tranquil forest stream at sunrise",
                    prompt_mode="structured",
                    run_mode="clip_by_clip",
                    continuity_mode="Motion Context (Chained)",
                    context_length="22",
                    steps=25,
                    cfg=1.0,
                    sampler="res_multistep",
                    scheduler="simple",
                    shift_video=12.0,
                    shift_audio=3.0,
                    seed=42,
                )

                images, audio, video, pos, lat, prompt_out, fps, fc, status = result
                self.assertEqual(pos, mock_positive)
                self.assertEqual(lat, mock_latent)
                self.assertEqual(fps, 24.0)
                self.assertEqual(fc, 124)
                self.assertIn("Emitted conditioning for FL2VA", status)

    def test_modifier_nodes_construction(self):
        """Verify SelfLift, Refine, and FaceRefine output dictionaries."""
        selflift_node = MiniMaxH3DirectorSelfLift()
        sl_cfg, = selflift_node.build_config(lowres_scale=0.5, highres_steps=4, native_low_carry=True)
        self.assertTrue(sl_cfg["enabled"])
        self.assertEqual(sl_cfg["lowres_scale"], 0.5)
        self.assertEqual(sl_cfg["highres_steps"], 4)

        refine_node = MiniMaxH3DirectorRefine()
        rf_cfg, = refine_node.build_config(
            mode="upscale", steps=4, denoise=0.4, target_width=1792, target_height=1024, enable_tiling=True, tile_count=2
        )
        self.assertTrue(rf_cfg["enabled"])
        self.assertEqual(rf_cfg["mode"], "upscale")
        self.assertEqual(rf_cfg["target_width"], 1792)

        face_node = MiniMaxH3DirectorFaceRefine()
        fc_cfg, = face_node.build_config(prompt="portrait face", strength=0.3, crop_size=512)
        self.assertTrue(fc_cfg["enabled"])
        self.assertEqual(fc_cfg["crop_size"], 512)

    def test_bridges_and_tail_extract(self):
        """Verify Reference Bridge, Prompt Bridge, and Tail extraction."""
        ref_bridge = MiniMaxH3ReferenceBridge()
        img1 = torch.zeros(1, 64, 64, 3)
        img2 = torch.zeros(1, 64, 64, 3)
        pack, = ref_bridge.build_pack(image_1=img1, image_2=img2)
        self.assertIn("ref_image_1", pack)
        self.assertIn("ref_image_2", pack)
        self.assertNotIn("ref_image_3", pack)

        prompt_bridge = MiniMaxH3PromptBridge()
        p_pack, = prompt_bridge.build_pack("Shot 1 scene\nShot 2 scene\n\nShot 3 scene")
        self.assertEqual(len(p_pack["prompts"]), 3)

        tail_node = MiniMaxH3TailFromLatent()
        mock_samples = {
            "samples": (
                torch.zeros(1, 16, 37, 16, 16),  # 124 frames
                torch.zeros(1, 64, 207),
            )
        }
        tail_video, tail_audio, last_frame, count, duration = tail_node.extract(
            mock_samples, self.mock_vae, self.mock_audio_vae, tail_seconds=1.0, align_to_h3_grid=True
        )
        self.assertEqual(count, 22)  # 1.0s at 24fps snaps to 22 frames
        self.assertEqual(duration, 22 / 24.0)

    def test_continuity_tail_slicing_and_repack(self):
        """Verify video and audio latent slicing for Motion Context."""
        video_lat = torch.zeros(1, 16, 37, 24, 42)
        audio_lat = torch.zeros(1, 64, 207)
        latent_dict = repack_av_latent(video_lat, audio_lat)

        video_tail, audio_tail = slice_continuity_tail(latent_dict, context_frames=22, audio_context_frames=24)
        # For 22 frames, video latent t is 7
        self.assertEqual(video_tail.shape[2], 7)
        self.assertEqual(video_tail.shape[3:], (24, 42))
        self.assertTrue(audio_tail.shape[-1] > 0)

    def test_face_refine_mask_and_bbox(self):
        """Verify ellipse mask generation and bounding box calculations."""
        mask = generate_feathered_ellipse_mask(64, 64)
        self.assertEqual(mask.shape, (1, 64, 64, 1))
        # Center should be 1.0, edges should approach 0.0
        self.assertAlmostEqual(mask[0, 32, 32, 0].item(), 1.0, places=1)
        self.assertAlmostEqual(mask[0, 0, 0, 0].item(), 0.0, places=1)

        test_frame = torch.zeros(100, 200, 3)
        x1, y1, bw, bh = simple_face_detect_bbox(test_frame)
        self.assertTrue(bw % 32 == 0)
        self.assertTrue(bh % 32 == 0)

    def test_selflift_spatial_interpolation(self):
        """Verify 5D video latent spatial resize."""
        latent = torch.ones(1, 16, 7, 24, 42)
        resized = spatial_interpolate_video_latent(latent, target_h=48, target_w=84)
        self.assertEqual(resized.shape, (1, 16, 7, 48, 84))

    def test_malformed_timeline_and_builder_inputs(self):
        """Verify node execution is robust against malformed timeline and builder JSON."""
        node = MiniMaxH3MasterDirector()
        with patch("core.executor.get_native_h3_node") as mock_get_native:
            mock_native = MagicMock()
            mock_positive = [[torch.zeros(1, 768), {"minimax_refs": []}]]
            mock_latent = {"samples": (torch.zeros(1, 16, 7, 24, 42), torch.zeros(1, 64, 37))}
            mock_native.execute.return_value = (mock_positive, mock_latent)
            mock_get_native.return_value = mock_native

            # Pass completely invalid JSON strings and non-dict JSON
            out = node.execute(
                model=self.mock_model,
                video_vae=self.mock_vae,
                audio_vae=self.mock_audio_vae,
                clip=self.mock_clip,
                mode=MODE_REF2VA,
                execution_mode="Conditioning Guide Output",
                timeline_data="NOT A VALID JSON STRING",
                builder_state="[1, 2, 3]",  # A list instead of a dict
            )
            self.assertIsNotNone(out)
            self.assertEqual(len(out), 9)
            self.assertIn("Emitted conditioning for REF2VA", out[8])

    def test_project_manager_hash_and_cache_integrity(self):
        """Verify project serialization stays under 100KB and separates cache keys correctly."""
        cm = ProjectCacheManager(project_id="test_proj", base_dir="output/test_minimax_cache")
        clip_data_a = {"prompt": "Sunset over the mountains", "seed": 42, "width": 1344, "height": 768, "duration": 5.0}
        clip_data_b = {"prompt": "Sunset over the mountains", "seed": 43, "width": 1344, "height": 768, "duration": 5.0}
        
        fp_a = compute_clip_fingerprint(clip_data_a["prompt"], clip_data_a["duration"], clip_data_a["width"], clip_data_a["height"], clip_data_a["seed"])
        fp_b = compute_clip_fingerprint(clip_data_b["prompt"], clip_data_b["duration"], clip_data_b["width"], clip_data_b["height"], clip_data_b["seed"])
        
        # Changing seed must produce a completely different cache key
        self.assertNotEqual(fp_a, fp_b)
        
        # Test project serialization format
        proj_str = cm.serialize_project(
            project_id="test_proj",
            clips=[{"id": 0, "params": clip_data_a, "fingerprint": fp_a}],
            timeline={"tracks": []},
            metadata={"version": 1},
        )
        self.assertIn("MiniMax H3 Master Director Project", proj_str)
        # Verify size is tiny (less than 5KB)
        self.assertTrue(len(proj_str.encode("utf-8")) < 5000)


if __name__ == "__main__":
    unittest.main()

