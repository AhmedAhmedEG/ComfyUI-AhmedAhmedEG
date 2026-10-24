import tempfile
import unittest
import io
from pathlib import Path
from unittest.mock import patch

import av
import torch

from core.cache_manager import ProjectCacheManager
from core.preview import create_preview_plan,cached_preview_plan
from core.preview_segments import encode_fragment
from core.preview_export import export_cached_preview


class PreviewExport(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.manager=ProjectCacheManager('export',self.temp.name)
        self.state={'project_id':'export','clips':[{'id':'one'},{'id':'two'}]}
        for index,cid in enumerate(('one','two')):
            self.manager.store_clip_results(cid,cid,{'samples':torch.zeros(1)},
                {'waveform':torch.ones(1,2,48000)*(.1+index*.1),'sample_rate':48000},
                torch.full((24,32,64,3),.2+index*.5))
        self.manager.update_clip_metadata('two',{'trim_prefix':2,'previous_trim':1})

    def inventory(self):
        return {str(p.relative_to(self.root)):(p.stat().st_size,p.stat().st_mtime_ns)
                for p in self.root.rglob('*') if p.is_file()}

    def prepare(self,scope):
        info=create_preview_plan(self.state,scope,self.temp.name)
        for part in [*info['playback']['videos'],info['playback']['audio']]:
            encode_fragment('export',part['key'],self.temp.name)
        self.assertTrue(cached_preview_plan('export',scope,self.temp.name)['found'])
        self.assertFalse((Path(self.manager.project_dir)/'previews'/(info['key']+'.mp4')).exists())
        return info

    def test_restored_fragment_playback_downloads_latest_and_full_without_cache_mutations(self):
        for scope,frames in [('latest',22),('full',45)]:
            info=self.prepare(scope);before=self.inventory()
            with tempfile.TemporaryDirectory() as output:
                with patch('core.preview.encode_preview',side_effect=AssertionError('Cached packets should not be re-encoded')):
                    path=export_cached_preview('export',info['key'],output,self.temp.name)
                with av.open(path) as container:
                    video=list(container.decode(video=0))
                    self.assertEqual(len(video),frames)
                    self.assertEqual((video[0].width,video[0].height),(64,32))
                    self.assertAlmostEqual(float(video[-1].pts*video[-1].time_base),(frames-1)/24,places=4)
                with av.open(path) as container:
                    audio=list(container.decode(audio=0))
                    self.assertAlmostEqual(sum(f.samples for f in audio)/48000,frames/24,delta=.04)
            self.assertEqual(before,self.inventory())

    def test_unknown_revision_does_not_create_project(self):
        with tempfile.TemporaryDirectory() as output:
            with self.assertRaises(FileNotFoundError):
                export_cached_preview('missing','a'*64,output,self.temp.name)
        self.assertFalse((self.root/'missing').exists())

    def test_explicit_download_can_encode_missing_fragments_only_into_temporary_storage(self):
        info=create_preview_plan(self.state,'latest',self.temp.name);before=self.inventory()
        with tempfile.TemporaryDirectory() as output:
            path=export_cached_preview('export',info['key'],output,self.temp.name)
            self.assertEqual(Path(path).parent,Path(output))
            with av.open(path) as container:self.assertEqual(len(list(container.decode(video=0))),22)
        self.assertEqual(before,self.inventory())

    def test_mixed_canvas_fallback_replaces_partial_remux(self):
        self.manager.store_clip_results('two','wide',{'samples':torch.zeros(1)},
            decoded_frames=torch.ones((24,32,96,3)))
        info=self.prepare('full');before=self.inventory()
        with tempfile.TemporaryDirectory() as output:
            path=export_cached_preview('export',info['key'],output,self.temp.name)
            with av.open(path) as container:
                frames=list(container.decode(video=0))
                self.assertEqual(len(frames),48)
                self.assertEqual(frames[0].width,96)
        self.assertEqual(before,self.inventory())

    def test_http_download_after_restart_works_without_master_input(self):
        import ast,asyncio,os
        from aiohttp import web
        from aiohttp.test_utils import TestClient,TestServer
        tree=ast.parse((Path(__file__).resolve().parent.parent/'__init__.py').read_text(encoding='utf-8'))
        handler=next(n for n in ast.walk(tree) if isinstance(n,ast.AsyncFunctionDef) and n.name=='smart_preview_media')
        handler.decorator_list=[]
        for node in ast.walk(handler):
            if isinstance(node,ast.ImportFrom):node.level=0
        namespace={'web':web,'asyncio':asyncio,'os':os,'_PREVIEW_LOCKS':{}}
        exec(compile(ast.Module(body=[handler],type_ignores=[]),'actual_preview_download','exec'),namespace)
        info=self.prepare('full');before=self.inventory()
        async def check():
            app=web.Application();app.router.add_get('/media',namespace['smart_preview_media'])
            async with TestClient(TestServer(app)) as client:
                response=await client.get('/media',params={'project_id':'export','key':info['key'],'read_only':'1','download':'1'})
                self.assertEqual(response.status,200,await response.text() if response.status!=200 else '')
                self.assertIn('attachment',response.headers['Content-Disposition'])
                body=await response.read();self.assertEqual(len(body),int(response.headers['Content-Length']))
                with av.open(io.BytesIO(body)) as media:self.assertEqual(len(list(media.decode(video=0))),45)
        with patch('core.cache_manager.get_cache_root_dir',return_value=self.temp.name),patch('core.progress.master_preview_input',return_value=None):
            asyncio.run(check())
        self.assertEqual(before,self.inventory())


if __name__=='__main__':unittest.main()
