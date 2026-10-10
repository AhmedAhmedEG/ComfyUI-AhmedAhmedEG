import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from core.project import migrate_timeline, seed_string, merge_timeline, write_portable, read_portable
from core.forge import draft_prompts, apply_draft
from tests.mock_torch import setup_mock_torch_if_needed
torch = setup_mock_torch_if_needed()


class Consolidation(unittest.TestCase):
    def test_starter_uses_separate_preview_and_attention_switching(self):
        from nodes import NODE_CLASS_MAPPINGS
        workflow=json.loads((Path(__file__).resolve().parents[1]/'workflows/MiniMax H3 Start Here.json').read_text(encoding='utf-8'))
        master=next(n for n in workflow['nodes'] if n['type']=='MiniMaxH3MasterNode')
        player=next(n for n in workflow['nodes'] if n['type']=='MiniMaxH3SmartPreview')
        self.assertFalse(NODE_CLASS_MAPPINGS[master['type']].OUTPUT_NODE)
        self.assertTrue(NODE_CLASS_MAPPINGS[player['type']].OUTPUT_NODE)
        self.assertTrue(any(link[1]==master['id'] and link[2]==9 and link[3]==player['id'] for link in workflow['links']))
        self.assertEqual(sum(n['type']=='H3SLAAttention' for n in workflow['nodes']),2)
        self.assertTrue(any(n['type']=='ComfySwitchNode' for n in workflow['nodes']))
        self.assertTrue(any(n['type']=='MiniMaxH3RefPack' for n in workflow['nodes']))
        self.assertFalse(any(n['type']=='SaveVideo' for n in workflow['nodes']))

    def test_stock_loader_graph_preserves_cache_identity_across_reload(self):
        from core.provenance import record_graph_provenance
        from core.cache_manager import fingerprint_value
        from types import SimpleNamespace
        from unittest.mock import patch
        import sys
        with tempfile.TemporaryDirectory() as directory:
            weights = Path(directory) / "model.safetensors"
            weights.write_bytes(b"native checkpoint")
            prompt = {"5": {"inputs": {"ref2va_model": ["2", 0]}},
                      "2": {"class_type": "UNETLoader", "inputs": {"unet_name": "ref.safetensors", "weight_dtype": "default"}}}
            paths = SimpleNamespace(get_full_path_or_raise=lambda category, name: str(weights))
            left, right = SimpleNamespace(), SimpleNamespace()
            with patch.dict(sys.modules, {"folder_paths": paths}):
                record_graph_provenance(prompt, 5, ref2va_model=left)
                record_graph_provenance(prompt, "5", ref2va_model=right)
                self.assertEqual(fingerprint_value(left), fingerprint_value(right))
                weights.write_bytes(b"changed checkpoint")
                old_fingerprint = fingerprint_value(right)
                record_graph_provenance(prompt, "5", ref2va_model=right)
                self.assertEqual(fingerprint_value(right), old_fingerprint)
                right = SimpleNamespace()  # actual stock-loader reload
                record_graph_provenance(prompt, "5", ref2va_model=right)
                self.assertNotEqual(fingerprint_value(left), fingerprint_value(right))

    def test_provenance_does_not_guess_through_third_party_nodes(self):
        from core.provenance import record_graph_provenance
        from types import SimpleNamespace
        value = SimpleNamespace()
        prompt = {"5": {"inputs": {"model": ["2", 0]}},
                  "2": {"class_type": "SomeModelModifier", "inputs": {"unet_name": "guess.safetensors"}}}
        record_graph_provenance(prompt, 5, model=value)
        self.assertFalse(hasattr(value, "_mmx_provenance"))

    def test_forge_rejects_asset_and_validation_injection(self):
        from core.forge import parse_draft
        for field in ("source", "validated", "locked", "model_override", "ref_ids"):
            with self.assertRaisesRegex(ValueError,"Unsupported drafted fields"):
                parse_draft(json.dumps({"shots":[{"prompt":"action",field:True}]}),1)

    def test_portable_graph_assets_become_independent_references(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root); (root/"graph.png").write_bytes(b"graph asset")
            state = {"clips":[{"id":"one","ref_ids":["p1_image_1"]}],
                "available_refs":[{"id":"p1_image_1","type":"image","filename":"graph.png"}]}
            package = root/"project.mmxproj"; write_portable(state,str(root),package)
            imported = read_portable(package,str(root))
            self.assertEqual(imported["references"][0]["id"],"p1_image_1")
            self.assertEqual((root/imported["references"][0]["filename"]).read_bytes(),b"graph asset")

    def test_full_seed_range_survives_json_migration(self):
        state = migrate_timeline({"clips": [{"seed": 18446744073709551615}]})
        self.assertEqual(json.loads(json.dumps(state))["clips"][0]["seed"], "18446744073709551615")
        with self.assertRaises(ValueError): seed_string(float(2**64))

    def test_append_remaps_shared_and_local_references_without_mutating_inputs(self):
        original = {"clips": [{"id": "a"}], "references": [{"id": "r", "filename": "a.png"}]}
        incoming = {"clips": [{"id": "a", "ref_ids": ["r"]}], "references": [{"id": "r", "filename": "b.png"}], "shared_ref_ids": ["r"]}
        before = copy.deepcopy(incoming)
        merged = merge_timeline(original, incoming, "append")
        self.assertNotEqual(merged["clips"][0]["id"], merged["clips"][1]["id"])
        self.assertEqual(merged["clips"][1]["ref_ids"], [merged["references"][1]["id"]])
        self.assertEqual(incoming, before)

    def test_portable_round_trip_preserves_actual_asset_bytes(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root); source = root / "input"; source.mkdir()
            (source / "ref.png").write_bytes(b"image content")
            state = {"clips": [{"id": "clip", "source": {"filename": "ref.png"}}], "references": [{"id": "r", "filename": "ref.png"}]}
            path = root / "pack.mmxproj"; write_portable(state, str(source), path)
            restored = read_portable(path, str(source))
            filename = restored["references"][0]["filename"]
            self.assertEqual((source / filename).read_bytes(), b"image content")
            self.assertEqual(restored["clips"][0]["source"]["filename"], filename)
            self.assertEqual(state["references"][0]["filename"], "ref.png")

    def test_portable_rejects_traversal_before_writing(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("../escape", "bad")
            archive.writestr("project.json", '{}')
        stream.seek(0)
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                read_portable(stream, root)
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_forge_requires_apply_and_rejects_changed_context(self):
        state = {"clips": [{"id": "a", "prompt": "old", "ref_ids": ["ref"]}]}
        provider = lambda messages, **kw: [{"generated_text": '{"shots":[{"prompt":"new","duration":5}]}'}]
        draft = draft_prompts(state, "improve", backend="local", generator=provider)
        self.assertEqual(state["clips"][0]["prompt"], "old")
        result = apply_draft(state, draft)
        self.assertEqual(result["clips"][0]["ref_ids"], ["ref"])
        self.assertEqual(result["clips"][0]["prompt"], "new")
        state["clips"][0]["prompt"] = "edited"
        with self.assertRaisesRegex(ValueError, "context changed"):
            apply_draft(state, draft)

    def test_forge_sees_named_pool_references_and_rejects_changed_pool(self):
        seen = []
        def provider(messages, **kwargs):
            seen.extend(messages)
            return '{"shots":[{"prompt":"Alice turns","duration":5,"type":"REF2VA"}]}'
        state = {"clips":[], "available_refs":[{"id":"image_1", "name":"Alice", "type":"image", "filename":"alice.png"}]}
        draft = draft_prompts(state, "One shot", backend="local", generator=provider)
        self.assertIn("Alice", seen[0]["content"])
        state["available_refs"][0]["filename"] = "someone_else.png"
        with self.assertRaisesRegex(ValueError,"context changed"):
            apply_draft(state,draft)

    def test_failed_cache_commit_does_not_replace_a_previous_take(self):
        from unittest.mock import patch
        from core.cache_manager import ProjectCacheManager
        with tempfile.TemporaryDirectory() as root:
            manager = ProjectCacheManager("project",root)
            manager.store_clip_results("shot","old",{"samples":torch.zeros((1,24,2,2,2))},
                {"waveform":torch.zeros((1,2,100)),"sample_rate":48000},torch.zeros((5,32,32,3)))
            old_path = manager.get_clip_latent_path("shot")
            original = manager._atomic_save
            calls = []
            def fail_second(value,path):
                calls.append(path)
                if len(calls) == 2: raise OSError("disk full")
                original(value,path)
            with patch.object(manager,"_atomic_save",side_effect=fail_second):
                with self.assertRaises(OSError):
                    manager.store_clip_results("shot","new",{"samples":torch.ones((1,24,2,2,2))},
                        {"waveform":torch.ones((1,2,100)),"sample_rate":48000})
            fresh = ProjectCacheManager("project",root)
            self.assertEqual(fresh.get_clip_latent_path("shot"),old_path)
            self.assertTrue(fresh.is_clip_cached_and_valid("shot","old"))
            self.assertEqual(float(fresh.load_clip_latent("shot")["samples"].sum()),0.)

    def test_checkpoint_provenance_is_stable_across_new_live_objects(self):
        from types import SimpleNamespace
        from core.cache_manager import fingerprint_value
        from core.provenance import record_provenance
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/"model.safetensors"; path.write_bytes(b"checkpoint")
            left = record_provenance(SimpleNamespace(),path,weight_dtype="default")
            right = record_provenance(SimpleNamespace(),path,weight_dtype="default")
            self.assertEqual(fingerprint_value(left),fingerprint_value(right))
            right.patches = {"weight":torch.ones((2,2))}
            self.assertNotEqual(fingerprint_value(left),fingerprint_value(right))
