"""Comprehensive mock-pipeline test suite for MiniMax H3 Master Director.

Validates the full execution flow, multi-segment continuity, conditioning generation,
lightweight project serialization, and modifier nodes WITHOUT downloading any physical models.
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch
pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if pkg_root not in sys.path:
    sys.path.insert(0, pkg_root)

from tests.mock_torch import setup_mock_torch_if_needed
torch = setup_mock_torch_if_needed()

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
        elif latent_tensor.ndim in (2, 3, 4):
            # Audio latent decode (outputs [B, samples, channels] before movedim)
            samples = latent_tensor.shape[-1] * 800
            return torch.zeros((1, samples, 2), dtype=torch.float32)
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
        self.director = MiniMaxH3MasterDirector()

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
                self.assertIn("Emitted conditioning for 1 clip(s)", status)

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
            self.assertIn("Emitted conditioning for 1 clip(s)", out[8])

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

    def test_refine_pass_and_spatial_tiling(self):
        """Verify second-pass refinement and spatial tiled sampling calculations."""
        from core.refine import apply_refine_pass, spatial_tiled_sample

        video = torch.ones((1, 16, 7, 24, 42), dtype=torch.float32)
        audio = torch.zeros((1, 32, 2, 12), dtype=torch.float32)
        latent_dict = {"samples": (video, audio)}

        # 1. Latent upscale mode without sampling
        upscaled = apply_refine_pass(
            model=self.mock_model,
            latent_dict=latent_dict,
            positive=[],
            negative=[],
            seed=0,
            refine_mode="latent_upscale",
            target_width=1344,
            target_height=768,
        )
        res_v = upscaled["samples"][0]
        # 768 // 16 = 48, 1344 // 16 = 84
        self.assertEqual(res_v.shape, (1, 16, 7, 48, 84))

        # 2. Tiled sampling logic
        with patch("comfy.sample.sample") as mock_sample:
            mock_sample.side_effect = lambda m, l, st, c, s, sc, p, n, sd, **kw: l
            tiled_res = spatial_tiled_sample(
                model=self.mock_model,
                latent_dict=latent_dict,
                steps=3,
                cfg=1.0,
                sampler_name="euler",
                scheduler="simple",
                positive=[],
                negative=[],
                seed=0,
                denoise=0.45,
                tile_count=2,
                tile_overlap=64,
            )
            self.assertEqual(tiled_res["samples"][0].shape, video.shape)

    def test_face_refinement_execution(self):
        """Verify face refinement pass and ultralytics detector detection fallback."""
        from core.face_refine import apply_face_refinement, detect_face_bbox_ultralytics

        frames = torch.ones((5, 128, 128, 3), dtype=torch.float32)
        # Without model/vae (unsharp fallback pass)
        stitched, orig = apply_face_refinement(frames, strength=0.35)
        self.assertEqual(stitched.shape, frames.shape)
        self.assertEqual(orig.shape, frames.shape)

        # With mock model and vae
        with patch("comfy.sample.sample") as mock_sample:
            mock_sample.side_effect = lambda *args, **kwargs: args[1] if len(args) > 1 else kwargs.get("latent_dict")
            stitched_model, _ = apply_face_refinement(
                frames, model=self.mock_model, vae=self.mock_vae, clip=self.mock_clip, strength=0.35
            )
            self.assertEqual(stitched_model.shape, frames.shape)

    def test_per_clip_seed_and_tail(self):
        """Verify per-clip custom seed and tail_seconds are properly respected."""
        timeline_data = json.dumps({
            "version": 1,
            "clips": [
                {
                    "id": "c1",
                    "name": "Shot 1",
                    "type": "T2V",
                    "duration": 5.0,
                    "seed": 99999,
                    "seed_mode": "increment",
                    "tail_seconds": 0.75,
                    "validated": False,
                    "prompt": "First clip",
                },
                {
                    "id": "c2",
                    "name": "Shot 2",
                    "type": "T2V",
                    "duration": 5.0,
                    "seed": 12345,
                    "seed_mode": "fixed",
                    "tail_seconds": 0.5,
                    "validated": False,
                    "prompt": "Second clip",
                }
            ]
        })

        with patch("core.executor.get_native_h3_node") as mock_get_native, \
             patch("comfy.sample.sample") as mock_sample:
            mock_native = MagicMock()
            mock_native.execute.return_value = ([[torch.zeros(1, 768), {}]], {"samples": (torch.zeros((1, 16, 7, 24, 42)), torch.zeros((1, 64, 37)))})
            mock_get_native.return_value = mock_native

            sampled_seeds = []
            def record_sample(*args, **kwargs):
                s = kwargs.get("seed") if "seed" in kwargs else (args[8] if len(args) > 8 else None)
                sampled_seeds.append(s)
                return {"samples": (torch.zeros((1, 16, 5, 16, 16)), torch.zeros((1, 32, 2, 4)))}

            mock_sample.side_effect = record_sample

            res = self.director.execute(
                model=self.mock_model,
                video_vae=self.mock_vae,
                audio_vae=self.mock_audio_vae,
                clip=self.mock_clip,
                timeline_data=timeline_data,
            )
            self.assertEqual(sampled_seeds, [99999, 12345])

    def test_validated_clip_caching_and_skip(self):
        """Verify validated clip skips diffusion sampling when cached on disk."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            cm = ProjectCacheManager(project_id="test_val_cache", base_dir=tmp_dir)
            
            # Pre-store cached frames for c1
            clip_prompt = "Cached first clip"
            c1_fp = compute_clip_fingerprint(clip_prompt, 5.0, 1344, 768, 777, model_name="h3")
            cached_frames = torch.ones((5, 256, 256, 3), dtype=torch.float32)
            cached_audio = {"waveform": torch.zeros((1, 2, 48000)), "sample_rate": 48000}
            cached_latent = {"samples": (torch.zeros((1, 16, 5, 16, 16)), torch.zeros((1, 32, 2, 4)))}
            cm.store_clip_results(
                clip_id="c1",
                fingerprint=c1_fp,
                latent_dict=cached_latent,
                audio_dict=cached_audio,
                decoded_frames=cached_frames,
                validated=True,
            )

            timeline_data = json.dumps({
                "version": 1,
                "clips": [
                    {
                        "id": "c1",
                        "name": "Shot 1",
                        "type": "T2V",
                        "duration": 5.0,
                        "seed": 777,
                        "validated": True,
                        "prompt": clip_prompt,
                    },
                    {
                        "id": "c2",
                        "name": "Shot 2",
                        "type": "T2V",
                        "duration": 5.0,
                        "seed": 888,
                        "validated": False,
                        "prompt": "Unvalidated second clip",
                    }
                ]
            })

            with patch("core.cache_manager.get_cache_root_dir", return_value=tmp_dir), \
                 patch("core.executor.get_native_h3_node") as mock_get_native, \
                 patch("comfy.sample.sample") as mock_sample:
                mock_native = MagicMock()
                mock_native.execute.return_value = ([[torch.zeros(1, 768), {}]], {"samples": (torch.zeros((1, 16, 7, 24, 42)), torch.zeros((1, 64, 37)))})
                mock_get_native.return_value = mock_native

                sampled_seeds = []
                def record_sample(*args, **kwargs):
                    s = kwargs.get("seed") if "seed" in kwargs else (args[8] if len(args) > 8 else None)
                    sampled_seeds.append(s)
                    return {"samples": (torch.zeros((1, 16, 5, 16, 16)), torch.zeros((1, 32, 2, 4)))}
                mock_sample.side_effect = record_sample

                res = self.director.execute(
                    model=self.mock_model,
                    video_vae=self.mock_vae,
                    audio_vae=self.mock_audio_vae,
                    clip=self.mock_clip,
                    timeline_data=timeline_data,
                    config={"project_id": "test_val_cache"},
                )
                # Only shot 2 (seed 888) should have been sampled! Shot 1 was skipped from cache!
                self.assertEqual(sampled_seeds, [888])

    def test_preview_mode_unvalidated_only(self):
        """Verify preview_mode='unvalidated' returns only unvalidated clips."""
        timeline_data = json.dumps({
            "version": 1,
            "preview_mode": "unvalidated",
            "clips": [
                {
                    "id": "c1",
                    "name": "Shot 1",
                    "type": "T2V",
                    "duration": 5.0,
                    "seed": 111,
                    "validated": True,
                    "prompt": "Shot 1 validated",
                },
                {
                    "id": "c2",
                    "name": "Shot 2",
                    "type": "T2V",
                    "duration": 5.0,
                    "seed": 222,
                    "validated": False,
                    "prompt": "Shot 2 new",
                }
            ]
        })

        with patch("core.executor.get_native_h3_node") as mock_get_native, \
             patch("comfy.sample.sample") as mock_sample:
            mock_native = MagicMock()
            mock_native.execute.return_value = ([[torch.zeros(1, 768), {}]], {"samples": (torch.zeros((1, 16, 7, 24, 42)), torch.zeros((1, 64, 37)))})
            mock_get_native.return_value = mock_native

            mock_sample.side_effect = lambda *args, **kwargs: {"samples": (torch.zeros((1, 16, 5, 16, 16)), torch.zeros((1, 32, 2, 4)))}

            res = self.director.execute(
                model=self.mock_model,
                video_vae=self.mock_vae,
                audio_vae=self.mock_audio_vae,
                clip=self.mock_clip,
                timeline_data=timeline_data,
            )
            # Output frames should only contain Shot 2's frames (5 frames, not 10 frames)
            final_frames = res[0]
            self.assertEqual(final_frames.shape[0], 5)

    def test_lazy_evaluation_status(self):
        """Verify check_lazy_status requests fl2va_model and ref2va_model only when relevant."""
        # 1. Timeline with only T2V (FL2VA)
        tl_fl2va = json.dumps({"clips": [{"type": "T2V"}]})
        req_fl2va = self.director.check_lazy_status(timeline_data=tl_fl2va)
        self.assertIn("fl2va_model", req_fl2va)
        self.assertNotIn("ref2va_model", req_fl2va)

        # 2. Timeline with only REF2VA
        tl_ref2va = json.dumps({"clips": [{"type": "REF2VA"}]})
        req_ref2va = self.director.check_lazy_status(timeline_data=tl_ref2va)
        self.assertIn("ref2va_model", req_ref2va)
        self.assertNotIn("fl2va_model", req_ref2va)

        # 3. Timeline with both
        tl_both = json.dumps({"clips": [{"type": "T2V"}, {"type": "REF2VA"}]})
        req_both = self.director.check_lazy_status(timeline_data=tl_both)
        self.assertIn("fl2va_model", req_both)
        self.assertIn("ref2va_model", req_both)

    def test_structured_prompt_key_aliases(self):
        """Verify prompt parsing supports both soundscape/overall_soundscape and music/non_diegetic_music."""
        # Test with legacy keys: soundscape, music
        tl_legacy = json.dumps({
            "clips": [{
                "type": "T2V",
                "prompt_mode": "structured",
                "structured_prompt": {
                    "imd": "A serene beach",
                    "soundscape": "Gentle ocean waves",
                    "music": "Acoustic guitar melody",
                }
            }]
        })

        with patch("core.executor.get_native_h3_node") as mock_get_native:
            mock_native = MagicMock()
            mock_native.execute.return_value = ([[torch.zeros(1, 768), {}]], {"samples": (torch.zeros((1, 16, 7, 24, 42)), torch.zeros((1, 64, 37)))})
            mock_get_native.return_value = mock_native

            res = self.director.execute(
                model=self.mock_model,
                video_vae=self.mock_vae,
                audio_vae=self.mock_audio_vae,
                clip=self.mock_clip,
                timeline_data=tl_legacy,
                execution_mode="Conditioning Guide Output",
            )
            emitted_prompt = res[5]
            self.assertIn("Gentle ocean waves", emitted_prompt)
            self.assertIn("Acoustic guitar melody", emitted_prompt)

    def test_seam_continuity_duplicate_frame_trimming(self):
        """Verify chained clips have duplicate frame 0 trimmed upon concatenation, preventing frozen frame."""
        tl_chained = json.dumps({
            "clips": [
                {"id": "c1", "type": "T2V", "duration": 5.0, "seed": 100, "continuity": True},
                {"id": "c2", "type": "I2V", "duration": 5.0, "seed": 200, "continuity": True},
            ]
        })

        with patch("core.executor.get_native_h3_node") as mock_get_native, \
             patch("comfy.sample.sample") as mock_sample:
            mock_native = MagicMock()
            mock_native.execute.return_value = ([[torch.zeros(1, 768), {}]], {"samples": (torch.zeros((1, 16, 7, 24, 42)), torch.zeros((1, 64, 37)))})
            mock_get_native.return_value = mock_native

            mock_sample.side_effect = lambda *args, **kwargs: {"samples": (torch.zeros((1, 16, 5, 16, 16)), torch.zeros((1, 32, 2, 4)))}

            res = self.director.execute(
                model=self.mock_model,
                video_vae=self.mock_vae,
                audio_vae=self.mock_audio_vae,
                clip=self.mock_clip,
                timeline_data=tl_chained,
            )
            final_frames = res[0]
            # 5 frames from c1 + (5 - 1) frames from c2 = 9 frames
            self.assertEqual(final_frames.shape[0], 9)

    def test_v2v_multi_reference_routing_and_prompt(self):
        """Verify V2V clips can accept multiple references (image, video, audio) and use reference prompt structure."""
        tl_v2v = json.dumps({
            "clips": [{
                "id": "c1",
                "type": "V2V",
                "duration": 5.0,
                "prompt_mode": "structured",
                "structured_prompt": {
                    "subject_definitions": "<Subject 1> is the character in <Picture 1>.\n<Video 1> provides dynamic motion.",
                    "summary": "[reference generation] V2V sequence",
                    "retention_analysis": "<Subject 1>: fully_preserved.",
                    "detailed_description": "Transform scene motion while preserving character identity.",
                    "overall_soundscape": "Wind rustling trees",
                    "non_diegetic_music": "Low strings",
                },
                "ref_ids": ["img_1", "vid_1", "aud_1"],
            }]
        })

        ref_pack = {
            "refs": [
                {"id": "img_1", "type": "image", "data": torch.zeros((1, 64, 64, 3))},
                {"id": "vid_1", "type": "video", "data": torch.zeros((5, 64, 64, 3))},
                {"id": "aud_1", "type": "audio", "data": {"waveform": torch.zeros((1, 2, 48000)), "sample_rate": 48000}},
            ]
        }

        with patch("core.executor.get_native_h3_node") as mock_get_native:
            mock_native = MagicMock()
            mock_native.execute.return_value = ([[torch.zeros(1, 768), {}]], {"samples": (torch.zeros((1, 16, 7, 24, 42)), torch.zeros((1, 64, 37)))})
            mock_get_native.return_value = mock_native

            res = self.director.execute(
                model=self.mock_model,
                video_vae=self.mock_vae,
                audio_vae=self.mock_audio_vae,
                clip=self.mock_clip,
                timeline_data=tl_v2v,
                ref_pack=ref_pack,
                execution_mode="Conditioning Guide Output",
            )
            # Verify prompt contains reference structure
            emitted_prompt = res[5]
            self.assertIn("subject_definitions:", emitted_prompt)
            self.assertIn("retention_analysis:", emitted_prompt)
            self.assertIn("detailed_description:", emitted_prompt)

            # Verify native node was called with ref_images, ref_videos, ref_audios
            call_kwargs = mock_native.execute.call_args[1]
            self.assertIn("ref_image_1", call_kwargs["ref_images"])
            self.assertIn("ref_video_1", call_kwargs["ref_videos"])
            self.assertIn("ref_audio_1", call_kwargs["ref_audios"])

    def test_extender_prev_samples_chaining(self):
        """Verify MiniMaxH3Extender extracts tail frame from prev_samples and passes to director."""
        from nodes.node_tritant_compat import MiniMaxH3Extender
        extender = MiniMaxH3Extender()

        prev_samples = {
            "samples": (
                torch.zeros((1, 16, 7, 16, 16)),
                torch.zeros((1, 32, 2, 12)),
            )
        }

        with patch("core.executor.get_native_h3_node") as mock_get_native, \
             patch("comfy.sample.sample") as mock_sample:
            mock_native = MagicMock()
            mock_native.execute.return_value = ([[torch.zeros(1, 768), {}]], {"samples": (torch.zeros((1, 16, 7, 24, 42)), torch.zeros((1, 64, 37)))})
            mock_get_native.return_value = mock_native

            mock_sample.side_effect = lambda *args, **kwargs: {"samples": (torch.zeros((1, 16, 5, 16, 16)), torch.zeros((1, 32, 2, 4)))}

            images, audio, samples = extender.extend(
                model=self.mock_model,
                vae=self.mock_vae,
                audio_vae=self.mock_audio_vae,
                clip=self.mock_clip,
                prompt="Continuation shot",
                duration=5.0,
                prev_samples=prev_samples,
            )
            self.assertIsNotNone(images)
            self.assertIsNotNone(samples)


if __name__ == "__main__":
    unittest.main()

