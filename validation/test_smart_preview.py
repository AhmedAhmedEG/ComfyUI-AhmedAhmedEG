"""Real clip-only/full preview encoding, cache revisions, and context trimming."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import av
import torch

from core.cache_manager import ProjectCacheManager
from core.preview import create_preview_plan, encode_preview, preview_path


class SmartPreview(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.manager = ProjectCacheManager("preview_test", self.temp.name)
        self.state = {"project_id": "preview_test", "clips": [
            {"id": "one", "name": "First"}, {"id": "two", "name": "Second"}, {"id": "pending"}]}
        for cid, value in [("one", .2), ("two", .8)]:
            self.manager.store_clip_results(cid, cid, {"samples": torch.zeros((1, 1, 2, 4, 4))},
                {"waveform": torch.ones((1, 2, 24000))*.1, "sample_rate": 48000},
                torch.ones((12, 32, 64, 3))*value)
        self.manager.update_clip_metadata("two", {"trim_prefix": 2, "previous_trim": 1})

    def plan(self, scope="latest"):
        return create_preview_plan(self.state, scope, self.temp.name)

    def encode(self, plan):
        return encode_preview(plan["project_id"], plan["key"], self.temp.name)

    def test_latest_loads_only_new_clip_and_is_a_separate_small_video(self):
        latest = self.plan(); full = self.plan("full")
        self.assertEqual(latest["clip_ids"], ["two"])
        self.assertEqual(full["clip_ids"], ["one", "two"])
        self.assertEqual(full["total_clips"], 3)
        load = torch.load
        paths = []
        def track(path, **kwargs):
            paths.append(str(path)); return load(path, **kwargs)
        with patch("torch.load", side_effect=track):
            latest_path = self.encode(latest)
        self.assertFalse(any("clip_one_" in path for path in paths), paths)
        full_path = self.encode(full)
        self.assertNotEqual(latest_path, full_path)
        with av.open(latest_path) as video:
            frames = list(video.decode(video=0))
            self.assertEqual(len(frames), 10)
            self.assertGreater(frames[0].to_ndarray(format="rgb24").mean(), 170)
            self.assertEqual(video.streams.video[0].codec_context.name, "h264")
            self.assertEqual(video.streams.audio[0].codec_context.name, "aac")
        with av.open(full_path) as video:
            frames = list(video.decode(video=0))
            self.assertEqual(len(frames), 21)
            self.assertLess(frames[0].to_ndarray(format="rgb24").mean(), 70)
        before = Path(latest_path).stat().st_mtime_ns
        with patch("torch.load", side_effect=AssertionError("Cached preview should not load tensors")):
            self.assertEqual(self.encode(latest), latest_path)
        self.assertEqual(Path(latest_path).stat().st_mtime_ns, before)

    def test_saved_revision_survives_a_later_generation(self):
        old = self.plan()
        self.manager.store_clip_results("two", "new", {"samples": torch.zeros((1, 1, 2, 4, 4))},
            decoded_frames=torch.zeros((5, 32, 64, 3)))
        new = self.plan()
        self.assertNotEqual(old["key"], new["key"])
        with av.open(self.encode(old)) as video:
            self.assertEqual(len(list(video.decode(video=0))), 10)
        with av.open(self.encode(new)) as video:
            self.assertEqual(len(list(video.decode(video=0))), 5)

    def test_info_is_lazy_and_missing_clips_are_not_substituted(self):
        plan = self.plan()
        _, media = preview_path(plan["project_id"], plan["key"], self.temp.name)
        self.assertFalse(media.exists())
        self.state["clips"] = [{"id": "pending"}]
        self.assertFalse(self.plan()["found"])

    def test_invalid_scope_and_paths_are_rejected(self):
        with self.assertRaises(ValueError): self.plan("anything")
        with self.assertRaises(ValueError): preview_path("../outside", "a"*64, self.temp.name)
        with self.assertRaises(ValueError): preview_path("preview_test", "../outside", self.temp.name)

    def test_media_route_supports_range_download_and_rejects_bad_keys(self):
        import ast
        import asyncio
        import weakref
        from aiohttp import web
        from aiohttp.test_utils import TestClient, TestServer
        # Isolate the actual package route from ComfyUI's GPU-only imports.
        tree = ast.parse((Path(__file__).resolve().parent.parent / "__init__.py").read_text(encoding="utf-8"))
        handler = next(node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef) and node.name == "smart_preview_media")
        handler.decorator_list = []
        for node in ast.walk(handler):
            if isinstance(node, ast.ImportFrom): node.level = 0
        namespace = {"asyncio": asyncio, "web": web, "_PREVIEW_LOCKS": weakref.WeakValueDictionary()}
        exec(compile(ast.Module(body=[handler], type_ignores=[]), "actual_preview_route", "exec"), namespace)
        plan = self.plan()
        async def check():
            app = web.Application(); app.router.add_get("/media", namespace["smart_preview_media"])
            async with TestClient(TestServer(app)) as client:
                query = {"project_id": plan["project_id"], "key": plan["key"]}
                response = await client.get("/media", params=query, headers={"Range": "bytes=0-127"})
                self.assertEqual(response.status, 206)
                self.assertEqual(response.headers["Content-Type"], "video/mp4")
                self.assertTrue(response.headers["Content-Range"].startswith("bytes 0-127/"))
                self.assertEqual(len(await response.read()), 128)
                response = await client.get("/media", params={**query, "download": "1"})
                self.assertEqual(response.status, 200)
                self.assertIn("attachment", response.headers["Content-Disposition"])
                response = await client.get("/media", params={**query, "key": "../outside"})
                self.assertEqual(response.status, 404)
        with patch("core.cache_manager.get_cache_root_dir", return_value=self.temp.name):
            asyncio.run(check())


if __name__ == "__main__": unittest.main()
