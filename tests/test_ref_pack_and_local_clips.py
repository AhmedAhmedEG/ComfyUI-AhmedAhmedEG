"""Unit tests for MiniMaxH3RefPack, clip-driven modes, and internal continuity."""

import unittest
import json

import os
import sys

pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if pkg_root not in sys.path:
    sys.path.insert(0, pkg_root)

from tests.mock_torch import setup_mock_torch_if_needed
torch = setup_mock_torch_if_needed()

from nodes.node_ref_pack import MiniMaxH3RefPack
from nodes.node_bridges import MiniMaxH3ReferenceBridge
from nodes.node_director import MiniMaxH3MasterDirector


class TestRefPackAndClipModes(unittest.TestCase):
    def setUp(self):
        self.ref_pack_node = MiniMaxH3RefPack()
        self.bridge_node = MiniMaxH3ReferenceBridge()
        self.director_node = MiniMaxH3MasterDirector()

    def test_ref_pack_creation_and_chaining(self):
        # Create dummy tensors
        img1 = torch.zeros((1, 64, 64, 3), dtype=torch.float32)
        img2 = torch.ones((1, 64, 64, 3), dtype=torch.float32)
        aud1 = {"waveform": torch.zeros((1, 2, 48000)), "sample_rate": 48000}

        # Pack 1
        pack1, = self.ref_pack_node.pack(
            image_1=img1,
            label_img_1="Hero Character",
            audio_1=aud1,
            label_aud_1="Hero Voice",
        )
        self.assertIn("refs", pack1)
        self.assertEqual(len(pack1["refs"]), 2)
        self.assertEqual(pack1["refs"][0]["name"], "Hero Character")
        self.assertEqual(pack1["refs"][0]["type"], "image")
        self.assertEqual(pack1["refs"][1]["name"], "Hero Voice")
        self.assertEqual(pack1["refs"][1]["type"], "audio")

        # Daisy chain into Pack 2
        pack2, = self.ref_pack_node.pack(
            ref_pack_optional=pack1,
            image_1=img2,
            label_img_1="Villain Character",
        )
        self.assertEqual(len(pack2["refs"]), 3)
        self.assertEqual(pack2["refs"][0]["name"], "Hero Character")
        self.assertEqual(pack2["refs"][2]["name"], "Villain Character")

    def test_reference_bridge_mmx_format(self):
        img = torch.zeros((1, 64, 64, 3), dtype=torch.float32)
        pack, = self.bridge_node.build_pack(ref_1=img)
        self.assertIn("refs", pack)
        self.assertEqual(len(pack["refs"]), 1)
        self.assertEqual(pack["refs"][0]["id"], "ref_img_1")

    def test_director_conditioning_guide_multi_clip(self):
        # Create RefPack with 2 images
        img1 = torch.zeros((1, 64, 64, 3), dtype=torch.float32)
        img2 = torch.ones((1, 64, 64, 3), dtype=torch.float32)
        pack, = self.ref_pack_node.pack(
            image_1=img1,
            label_img_1="Hero",
            image_2=img2,
            label_img_2="Sidekick",
        )

        ref_id_1 = pack["refs"][0]["id"]
        ref_id_2 = pack["refs"][1]["id"]

        # 3 Clips:
        # Clip 1: T2V (5.0s)
        # Clip 2: I2V (5.0s) using Hero
        # Clip 3: REF2VA (5.0s) using Sidekick
        timeline_data = json.dumps({
            "version": 2,
            "clips": [
                {
                    "id": "clip_1",
                    "name": "Shot 1",
                    "type": "T2V",
                    "duration": 5.0,
                    "prompt": "Cinematic establishing wide shot.",
                    "ref_ids": [],
                    "continuity": True,
                },
                {
                    "id": "clip_2",
                    "name": "Shot 2",
                    "type": "I2V",
                    "duration": 5.0,
                    "prompt": "Hero turns around.",
                    "ref_ids": [ref_id_1],
                    "continuity": True,
                },
                {
                    "id": "clip_3",
                    "name": "Shot 3",
                    "type": "REF2VA",
                    "duration": 5.0,
                    "prompt": "Sidekick speaks.",
                    "ref_ids": [ref_id_2],
                    "continuity": True,
                },
            ]
        })

        # Mock objects for CLIP, VAE
        class MockCLIP:
            def encode_from_tokens(self, *args, **kwargs):
                return (torch.zeros((1, 10, 5120)), torch.zeros((1, 5120)))
            def tokenize(self, *args, **kwargs):
                return {}

        class MockVAE:
            def encode(self, x):
                return torch.zeros((1, 16, 5, 8, 8))
            def decode(self, x):
                return torch.zeros((25, 64, 64, 3))

        mock_clip = MockCLIP()
        mock_vae = MockVAE()

        from unittest.mock import patch, MagicMock
        with patch("core.executor.get_native_h3_node") as mock_get_native:
            mock_native = MagicMock()
            mock_positive = [[torch.zeros(1, 768), {"minimax_keyframes": []}]]
            mock_latent = {"samples": (torch.zeros(1, 16, 7, 24, 42), torch.zeros(1, 64, 37))}
            mock_native.execute.return_value = (mock_positive, mock_latent)
            mock_get_native.return_value = mock_native

            res = self.director_node.execute(
                clip=mock_clip,
                video_vae=mock_vae,
                audio_vae=mock_vae,
                execution_mode="Conditioning Guide Output",
                width=256,
                height=256,
                duration=5.0,
                frame_rate=24.0,
                ref_pack=pack,
                timeline_data=timeline_data,
            )

        dummy_img, dummy_aud, video_info, pos, lat, prompt, fps, total_frames, status_str = res
        self.assertIn("Emitted conditioning for 3 clip(s)", status_str)
        self.assertEqual(fps, 24.0)

    def test_daisy_chained_ref_packs_with_unique_ids(self):
        """Verify that daisy-chaining multiple MiniMaxH3RefPack nodes produces unique IDs with pack prefixes."""
        img1 = torch.zeros((1, 64, 64, 3), dtype=torch.float32)
        img2 = torch.ones((1, 64, 64, 3), dtype=torch.float32)
        img3 = torch.zeros((1, 64, 64, 3), dtype=torch.float32)

        # Pack 1 (root)
        pack1, = self.ref_pack_node.pack(image_1=img1, label_img_1="Hero 1")
        self.assertEqual(pack1["pack_count"], 1)
        self.assertEqual(pack1["refs"][0]["id"], "img_1")

        # Pack 2 (chained from Pack 1)
        pack2, = self.ref_pack_node.pack(ref_pack_optional=pack1, image_1=img2, label_img_1="Hero 2")
        self.assertEqual(pack2["pack_count"], 2)
        # Pack 2 has 2 refs: img_1 from pack 1, and p2_img_1 from pack 2
        self.assertEqual(len(pack2["refs"]), 2)
        self.assertEqual(pack2["refs"][0]["id"], "img_1")
        self.assertEqual(pack2["refs"][1]["id"], "p2_img_1")
        self.assertEqual(pack2["refs"][1]["name"], "Hero 2")

        # Pack 3 (chained from Pack 2)
        pack3, = self.ref_pack_node.pack(ref_pack_optional=pack2, image_1=img3, label_img_1="Hero 3")
        self.assertEqual(pack3["pack_count"], 3)
        self.assertEqual(len(pack3["refs"]), 3)
        self.assertEqual(pack3["refs"][2]["id"], "p3_img_1")
        self.assertEqual(pack3["refs"][2]["name"], "Hero 3")

    def test_refmod_pooling_and_director_integration(self):
        """Verify RefMod models pool into ref_pack and are recognized by MasterDirector."""
        pack, = self.ref_pack_node.pack(
            refmod_1="character_cyberpunk.safetensors",
            label_mod_1="Cyberpunk Hero",
            refmod_2="style_anime.safetensors",
            label_mod_2="Anime Concept",
        )
        self.assertEqual(len(pack["refs"]), 2)
        self.assertEqual(pack["refs"][0]["type"], "refmod")
        self.assertEqual(pack["refs"][0]["name"], "Cyberpunk Hero")
        self.assertEqual(pack["refs"][0]["data"], "character_cyberpunk.safetensors")
        self.assertEqual(pack["refs"][1]["type"], "refmod")
        self.assertEqual(pack["refs"][1]["name"], "Anime Concept")

        # Test director execution with RefMods and unified REF2VA mode
        timeline_data = json.dumps({
            "version": 2,
            "clips": [
                {
                    "id": "clip_1",
                    "name": "Shot 1",
                    "type": "REF2V", # Unified to REF2VA
                    "duration": 5.0,
                    "prompt": "Scene featuring <Cyberpunk Hero> with high fidelity.",
                    "ref_ids": ["mod_1"],
                    "continuity": True,
                }
            ]
        })

        class MockCLIP:
            def encode_from_tokens(self, *args, **kwargs):
                return (torch.zeros((1, 10, 5120)), torch.zeros((1, 5120)))
            def tokenize(self, *args, **kwargs):
                return {}

        class MockVAE:
            def encode(self, x):
                return torch.zeros((1, 16, 5, 8, 8))
            def decode(self, x):
                return torch.zeros((25, 64, 64, 3))

        from unittest.mock import patch, MagicMock
        with patch("core.executor.get_native_h3_node") as mock_get_native:
            mock_native = MagicMock()
            mock_positive = [[torch.zeros(1, 768), {"minimax_keyframes": []}]]
            mock_latent = {"samples": (torch.zeros(1, 16, 7, 24, 42), torch.zeros(1, 64, 37))}
            mock_native.execute.return_value = (mock_positive, mock_latent)
            mock_get_native.return_value = mock_native

            res = self.director_node.execute(
                clip=MockCLIP(),
                video_vae=MockVAE(),
                audio_vae=MockVAE(),
                execution_mode="Conditioning Guide Output",
                ref_pack=pack,
                timeline_data=timeline_data,
            )

        dummy_img, dummy_aud, video_info, pos, lat, prompt_out, fps, total_frames, status_str = res
        self.assertIn("Emitted conditioning for 1 clip(s)", status_str)
        # Verify tag translation translated <Cyberpunk Hero> to <Picture 1> or appropriate tag
        self.assertIn("<Picture 1>", prompt_out)


if __name__ == "__main__":
    unittest.main()

