import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import torch
from core.cache_manager import ProjectCacheManager
from core.preview import create_preview_plan, cached_preview_plan, encode_preview
from core.progress import accept_preview_input, master_preview_input


class PreviewInputGate(unittest.TestCase):
    def test_unknown_project_restore_does_not_create_any_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'absent'
            self.assertFalse(cached_preview_plan('unknown',base_dir=root)['found'])
            self.assertFalse(root.exists())

    def test_restore_only_reads_existing_plans_and_encodes(self):
        with tempfile.TemporaryDirectory() as folder:
            manager=ProjectCacheManager('gate',folder)
            manager.store_clip_results('one','fp',{'samples':torch.zeros(1)},
                decoded_frames=torch.zeros((4,16,16,3)))
            info=create_preview_plan({'project_id':'gate','clips':[{'id':'one'}]},base_dir=folder)
            def inventory():
                return {str(p.relative_to(folder)):(p.stat().st_size,p.stat().st_mtime_ns)
                    for p in Path(folder).rglob('*') if p.is_file()}
            before=inventory()
            self.assertFalse(cached_preview_plan('gate',base_dir=folder)['found'])
            self.assertEqual(inventory(),before,'An unencoded plan must not trigger encoding')
            encode_preview('gate',info['key'],folder)
            before=inventory()
            result=cached_preview_plan('gate',base_dir=folder)
            self.assertTrue(result['found']);self.assertTrue(result['cache_read_only'])
            self.assertEqual(result['key'],info['key'])
            self.assertEqual(inventory(),before,'Restore must not write or delete server cache files')

    def test_http_requests_cannot_enable_cache_changes_without_master_input(self):
        import ast, asyncio, os, weakref
        from types import SimpleNamespace
        from aiohttp import web
        from aiohttp.test_utils import TestClient, TestServer
        tree=ast.parse((Path(__file__).resolve().parent.parent/'__init__.py').read_text(encoding='utf-8'))
        namespace={'web':web,'asyncio':asyncio,'os':os,'_PREVIEW_LOCKS':weakref.WeakValueDictionary()}
        for name in ['smart_preview_info','smart_preview_media','smart_preview_segment']:
            handler=next(n for n in ast.walk(tree) if isinstance(n,ast.AsyncFunctionDef) and n.name==name)
            handler.decorator_list=[]
            for n in ast.walk(handler):
                if isinstance(n,ast.ImportFrom):n.level=0
            exec(compile(ast.Module(body=[handler],type_ignores=[]),'actual_preview_routes','exec'),namespace)
        async def check(root):
            app=web.Application();app.router.add_post('/info',namespace['smart_preview_info'])
            app.router.add_get('/media',namespace['smart_preview_media']);app.router.add_get('/segment',namespace['smart_preview_segment'])
            async with TestClient(TestServer(app)) as client:
                response=await client.post('/info',json={'master_input':True,'timeline':{'project_id':'no-master','clips':[{'id':'draft'}]}})
                self.assertEqual(response.status,200);self.assertFalse((await response.json())['found'])
                for route in ['/media','/segment']:
                    response=await client.get(route,params={'project_id':'no-master','key':'a'*64})
                    self.assertEqual(response.status,404)
                self.assertFalse(root.exists(),'Metadata and media requests must not create a project before input')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'absent'
            with patch('core.cache_manager.get_cache_root_dir',return_value=str(root)), patch('core.progress.master_preview_input',return_value=None):
                asyncio.run(check(root))

    def test_only_published_master_state_is_used_and_is_detached_from_authoring(self):
        from core import progress
        with patch.object(progress,'_preview_inputs',__import__('collections').OrderedDict()):
            self.assertIsNone(master_preview_input('gate'))
            state={'project_id':'gate','clips':[{'id':'one'}]}
            accept_preview_input(state)
            state['clips'].append({'id':'draft'})
            self.assertEqual(len(master_preview_input('gate')['clips']),1)
            returned=master_preview_input('gate');returned['clips'].clear()
            self.assertEqual(len(master_preview_input('gate')['clips']),1)
            with self.assertRaises(ValueError):accept_preview_input({'project_id':'gate'})


if __name__=='__main__':unittest.main()
