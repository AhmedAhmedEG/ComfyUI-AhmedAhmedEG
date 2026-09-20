import os
import sys
import unittest
from unittest.mock import MagicMock, patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tests.mock_torch import setup_mock_torch_if_needed
torch = setup_mock_torch_if_needed()
from core.executor import decode_audio_latent, MasterDirectorExecutor
from core.face_refine import apply_face_refinement
from core.selflift import sample_selflift_progressive
from core.refine import spatial_tiled_sample
from core.cache_manager import ProjectCacheManager
from nodes.node_director import MiniMaxH3MasterDirector


class TestDeepValidation(unittest.TestCase):
    def test_decode_audio_latent_shapes(self):
        """Verify decode_audio_latent properly orients channels regardless of incoming dimension order."""
        audio_vae = MagicMock()
        audio_vae.audio_sample_rate = 32000

        # Case A: VAE decodes [1, 48000, 2] (samples at dim 1, channels at dim 2)
        audio_vae.decode.return_value = torch.zeros((1, 48000, 2))
        res_a = decode_audio_latent(audio_vae, torch.zeros((1, 32, 2, 100)))
        self.assertEqual(res_a["waveform"].shape, (1, 2, 48000))

        # Case B: VAE decodes [1, 2, 48000] (channels already at dim 1)
        audio_vae.decode.return_value = torch.zeros((1, 2, 48000))
        res_b = decode_audio_latent(audio_vae, torch.zeros((1, 32, 2, 100)))
        self.assertEqual(res_b["waveform"].shape, (1, 2, 48000))

        # Case C: 2D tensor [2, 48000]
        audio_vae.decode.return_value = torch.zeros((2, 48000))
        res_c = decode_audio_latent(audio_vae, torch.zeros((1, 32, 2, 100)))
        self.assertEqual(res_c["waveform"].shape, (1, 2, 48000))

    def test_refmod_latent_hw_indexing(self):
        """Verify RefMod image latent uses latent.shape[-2] and [-1] for height and width."""
        executor = MasterDirectorExecutor(project_id="test_deep_val")
        mock_clip = MagicMock()
        mock_clip.tokenize.return_value = {}
        mock_clip.encode_from_tokens_scheduled.return_value = ([[torch.zeros((1, 10, 5120)), {}]], None)

        mock_vae = MagicMock()
        mock_vae.decode.return_value = torch.zeros((1, 1, 64, 64, 3))
        mock_audio_vae = MagicMock()

        # Image latent 5D: [1, 24, 1, 48, 84] (T=1, H=48, W=84)
        img_latent = torch.zeros((1, 24, 1, 48, 84))
        refmod_items = [{
            "kind": "image",
            "name": "test_char",
            "latent": img_latent,
            "slot": 1,
        }]

        with patch("core.executor.get_native_h3_node") as mock_get_node:
            mock_native = MagicMock()
            mock_native.execute.return_value = ([[torch.zeros((1, 10, 5120)), {"minimax_refs": []}]], {"samples": None})
            mock_get_node.return_value = mock_native

            pos, lat, prompt = executor.build_conditioning(
                mode="REF2VA",
                prompt="test",
                width=1344,
                height=768,
                duration=5.0,
                clip=mock_clip,
                vae=mock_vae,
                audio_vae=mock_audio_vae,
                refmod_items=refmod_items,
            )

            meta = pos[0][1]
            refs = meta.get("minimax_refs", [])
            self.assertEqual(len(refs), 1)
            ref_block = refs[0]
            self.assertEqual(ref_block["kind"], "image")
            # Must be 48 and 84, NOT 1 (the time dim)!
            self.assertEqual(ref_block["latent_h"], 48)
            self.assertEqual(ref_block["latent_w"], 84)

    def test_ref2va_continuity_tail_injection(self):
        """Verify that REF2VA clips inherit previous tail when continuity is enabled and local refs are empty."""
        node = MiniMaxH3MasterDirector()
        mock_model = MagicMock()
        mock_model.clone.return_value = mock_model
        mock_model.model_options = {}

        mock_vae = MagicMock()
        mock_vae.decode.return_value = torch.zeros((5, 64, 64, 3))

        mock_audio_vae = MagicMock()
        mock_audio_vae.decode.return_value = torch.zeros((1, 2, 48000))
        mock_audio_vae.audio_sample_rate = 48000

        mock_clip = MagicMock()
        mock_clip.tokenize.return_value = {}
        mock_clip.encode_from_tokens_scheduled.return_value = ([[torch.zeros((1, 10, 5120)), {}]], None)

        timeline_data = """{
            "clips": [
                {"id": "c1", "type": "T2V", "duration": 1.0, "continuity": false, "validated": false},
                {"id": "c2", "type": "REF2VA", "duration": 1.0, "continuity": true, "validated": false, "ref_ids": []}
            ]
        }"""

        with patch("comfy.sample.sample") as mock_sample, \
             patch("core.executor.get_native_h3_node") as mock_get_node:
            mock_sample.return_value = {"samples": (torch.zeros((1, 24, 5, 48, 84)), torch.zeros((1, 32, 2, 40)))}
            mock_native = MagicMock()
            mock_native.execute.return_value = ([[torch.zeros((1, 10, 5120)), {"minimax_refs": []}]], {"samples": None})
            mock_get_node.return_value = mock_native

            res = node.execute(
                model=mock_model,
                video_vae=mock_vae,
                audio_vae=mock_audio_vae,
                clip=mock_clip,
                timeline_data=timeline_data,
            )

            self.assertEqual(mock_native.execute.call_count, 2)
            c2_call_kwargs = mock_native.execute.call_args_list[1][1]
            self.assertIn("ref_images", c2_call_kwargs)
            self.assertIn("ref_image_1", c2_call_kwargs["ref_images"])
            self.assertIsNotNone(c2_call_kwargs["ref_images"]["ref_image_1"])

    def test_face_refine_dimension_safeguard(self):
        """Verify apply_face_refinement resizes refined_crops if VAE decoder alters dimensions."""
        frames = torch.zeros((4, 256, 256, 3))
        mock_vae = MagicMock()
        mock_vae.encode.return_value = {"samples": torch.zeros((1, 24, 4, 8, 8))}
        mock_vae.decode.return_value = torch.zeros((4, 120, 120, 3))
        mock_model = MagicMock()

        with patch("comfy.sample.sample") as mock_sample:
            mock_sample.return_value = {"samples": (torch.zeros((1, 24, 4, 8, 8)), torch.zeros((1, 32, 2, 20)))}
            stitched, orig = apply_face_refinement(
                decoded_frames=frames,
                model=mock_model,
                vae=mock_vae,
                strength=0.5,
                crop_size=128,
            )
            self.assertEqual(stitched.shape, (4, 256, 256, 3))

    def test_concatenate_multichannel_audio(self):
        """Verify concatenate_audio_clips standardizes mono, stereo, and 6-channel audio to stereo."""
        from core.audio_post import concatenate_audio_clips
        clips = [
            {"waveform": torch.zeros((1, 48000)), "sample_rate": 48000},       # Mono
            {"waveform": torch.zeros((2, 48000)), "sample_rate": 48000},       # Stereo
            {"waveform": torch.zeros((6, 48000)), "sample_rate": 48000},       # 5.1 Surround
        ]
        result = concatenate_audio_clips(clips, target_sample_rate=48000)
        self.assertIn("waveform", result)
        self.assertEqual(result["waveform"].shape[0], 1)
        self.assertEqual(result["waveform"].shape[1], 2)  # Strictly stereo [1, 2, total_samples]


    def test_face_refine_boundary_clamping(self):
        """Verify face refinement handles small or odd-dimension frames at edges without index error."""
        frames = torch.zeros((2, 120, 150, 3))
        stitched, orig = apply_face_refinement(
            decoded_frames=frames,
            crop_size=512,
            strength=0.35,
        )
        self.assertEqual(stitched.shape, (2, 120, 150, 3))

    def test_refpack_daisy_chain_multi_packs(self):
        """Verify daisy-chaining multiple RefPacks accumulates references with unique IDs and pack indices."""
        from nodes.node_ref_pack import MiniMaxH3RefPack
        pack_node = MiniMaxH3RefPack()

        # Pack 1
        img1 = torch.zeros((1, 64, 64, 3))
        res1 = pack_node.pack(image_1=img1)[0]
        self.assertEqual(len(res1["refs"]), 1)
        self.assertEqual(res1["refs"][0]["id"], "image_1")
        self.assertEqual(res1["refs"][0]["name"], "image_1")

        # Pack 2 chained from Pack 1
        img2 = torch.zeros((1, 64, 64, 3))
        res2 = pack_node.pack(ref_pack_optional=res1, image_1=img2)[0]
        self.assertEqual(len(res2["refs"]), 2)
        self.assertEqual(res2["refs"][0]["id"], "image_1")
        self.assertEqual(res2["refs"][1]["id"], "p2_image_1")
        self.assertEqual(res2["refs"][1]["name"], "p2_image_1")
        self.assertEqual(res2["pack_count"], 2)


if __name__ == "__main__":
    unittest.main()

