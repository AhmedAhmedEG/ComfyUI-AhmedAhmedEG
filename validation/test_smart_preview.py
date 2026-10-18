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
    def test_all_saved_results_survive_approval_changes_and_run_epochs(self):
        for index, cid in enumerate(('three', 'four')):
            self.manager.begin_preview_run()
            self.manager.store_clip_results(cid, cid, {'samples': torch.zeros((1, 1, 2, 4, 4))},
                decoded_frames=torch.ones((12, 32, 64, 3))*(index+.3))
        self.state['clips'] = [{'id': cid, 'validated': False} for cid in ('one','two','three','four')]
        self.manager.begin_preview_run()  # Starting another run must not erase saved-result visibility.
        generation = self.manager._manifest['clips']['four']['generation']
        self.state['clips'][-1]['invalidated_generation'] = generation
        before = self.plan('full')
        self.assertEqual(before['clip_ids'], ['one','two','three','four'])
        self.state['clips'][0]['validated'] = True
        after = self.plan('full')
        self.assertEqual(before['key'], after['key'], 'Approval changes must not change preview contents or revision')
        with av.open(self.encode(after)) as video:
            self.assertEqual(sum(1 for _ in video.decode(video=0)), 45)

    def test_full_and_latest_update_after_each_clip_in_one_running_job(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from core import progress
        self.state['clips'] = [{'id': cid, 'validated': False} for cid in ('one','two','three','four')]
        graph = {'5': {'class_type':'MiniMaxH3MasterNode', 'inputs': {
            'generation_mode':'All clips', 'timeline_data':json.dumps(self.state)}}}
        queue=Mock();queue.get_current_queue.return_value=([(1,'dynamic-four',graph,{})],[])
        server=SimpleNamespace(instance=SimpleNamespace(prompt_queue=queue,send_sync=Mock()))
        with patch.dict('sys.modules', {'server':SimpleNamespace(PromptServer=server)}):
            for index, shot in enumerate(self.state['clips']):
                cid=shot['id'];progress.shot_event('5','preview_test',cid,'sampling')
                context=progress.preview_run_context('preview_test',self.state['clips'],queue)
                self.assertIn(cid,context['clip_ids'])
                self.manager.store_clip_results(cid, 'replacement', {'samples':torch.zeros((1,1,2,4,4))},
                    decoded_frames=torch.ones((5,32,64,3))*.5)
                progress.shot_event('5','preview_test',cid,'completed')
                context=progress.preview_run_context('preview_test',self.state['clips'],queue)
                full=create_preview_plan(self.state,'full',self.temp.name,run_context=context)
                latest=create_preview_plan(self.state,'latest',self.temp.name,run_context=context)
                self.assertEqual(full['clip_count'],max(2,index+1))
                self.assertEqual(latest['clip_ids'],[cid])
                with av.open(self.encode(full)) as video:
                    self.assertEqual(sum(1 for _ in video.decode(video=0)), 14 if index == 0 else 5*(index+1))

    def setUp(self):
        torch.set_num_threads(2)
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

    def test_replaced_preview_revision_is_deleted(self):
        old = self.plan()
        self.manager.store_clip_results("two", "new", {"samples": torch.zeros((1, 1, 2, 4, 4))},
            decoded_frames=torch.zeros((5, 32, 64, 3)))
        new = self.plan()
        self.assertNotEqual(old["key"], new["key"])
        with self.assertRaises(FileNotFoundError):self.encode(old)
        with av.open(self.encode(new)) as video:
            self.assertEqual(len(list(video.decode(video=0))), 5)

    def test_historical_take_scope_is_rejected(self):
        old_path = self.manager.get_clip_latent_path("one")
        self.manager.store_clip_results("one", "new", {"samples": torch.zeros((1, 1, 2, 4, 4))},
            decoded_frames=torch.ones((5, 32, 64, 3))*.9)
        self.assertFalse(Path(old_path).exists())
        with self.assertRaises(ValueError):create_preview_plan(self.state,"take",self.temp.name)
        self.assertNotIn('takes',self.manager._load_manifest())

    def test_mixed_resolution_full_preview_keeps_both_clips_at_original_canvas(self):
        self.manager.store_clip_results("two", "large", {"samples": torch.zeros((1, 1, 2, 4, 4))},
            decoded_frames=torch.ones((3, 736, 1280, 3))*.8)
        full=self.plan("full")
        self.assertEqual(full["clip_ids"],["one","two"])
        self.assertEqual(full["missing_clips"],[{"id":"pending","name":"pending"}])
        with av.open(self.encode(full)) as video:
            frames=list(video.decode(video=0));self.assertEqual(len(frames),15)
            self.assertEqual((video.streams.video[0].width,video.streams.video[0].height),(1280,736))
            self.assertLess(frames[0].to_ndarray(format="rgb24")[368,640].mean(),70)
            self.assertGreater(frames[-1].to_ndarray(format="rgb24")[368,640].mean(),170)
        small=create_preview_plan(self.state,"latest",self.temp.name,quality="540p")
        self.assertNotEqual(full["key"],small["key"])
        with av.open(self.encode(small)) as video:
            self.assertLessEqual(video.streams.video[0].height,540)
            self.assertLessEqual(video.streams.video[0].width,960)

    def test_info_is_lazy_and_missing_clips_are_not_substituted(self):
        plan = self.plan()
        _, media = preview_path(plan["project_id"], plan["key"], self.temp.name)
        self.assertFalse(media.exists())
        self.state["clips"] = [{"id": "pending"}]
        self.assertFalse(self.plan()["found"])

    def test_failed_encode_never_publishes_partial_media(self):
        plan = self.plan()
        _, target = preview_path(plan['project_id'], plan['key'], self.temp.name)
        def fail(path, *args, **kwargs):
            Path(path).write_bytes(b'partial mp4')
            raise RuntimeError('interrupted encode')
        with patch('core.vendor.dasiwa.helper_pyav_video.encode_attempt', side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, 'interrupted encode'):
                self.encode(plan)
        self.assertFalse(target.exists())
        with av.open(self.encode(plan)) as media:
            self.assertEqual(sum(1 for _ in media.decode(video=0)), 10)

    def test_full_preview_includes_locked_source_and_trims_its_handoff(self):
        self.state["clips"] = [{"id": "locked", "locked": True, "source": {"filename": "input.mp4"}}, {"id": "two"}]
        source = {"frames": torch.zeros((12, 32, 64, 3)), "audio": None}
        plan = self.plan("full")
        self.assertEqual(plan["clip_ids"], ["locked", "two"])
        with patch("core.source_media.source_range", return_value=source):
            with av.open(self.encode(plan)) as video:
                self.assertEqual(len(list(video.decode(video=0))), 21)

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
