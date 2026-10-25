import copy
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from tests.mock_torch import setup_mock_torch_if_needed
torch=setup_mock_torch_if_needed()
from core.cache_manager import ProjectCacheManager
from core.project_json import prepare_workflow
from core.project_bundle import write_bundle,read_bundle


class ProjectJSONTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.input=self.root/'input';self.input.mkdir()
        self.manager=ProjectCacheManager('editable',str(self.root/'cache'))
        self.timeline={'version':2,'project_id':'editable','approval_control_version':1,'draft_updated_at':42,
            'available_refs':[{'id':'image_1','name':'Hero','type':'image'}],
            'clips':[{'id':'one','duration':5,'prompt':'Original','seed':'18446744073709551615','validated':True,
                'saved_generation':'stale','cache_report':{'stats':{}},'selected':True}],
            'builder_state':'{"ref":{}}'}
        self.workflow={'nodes':[{'id':5,'type':'MiniMaxH3MasterNode','widgets_values':['old timeline'],
                'widgets_values_named':{'timeline_data':'stale duplicate','builder_state':'stale duplicate'}},
            {'id':6,'type':'LoadImage','widgets_values':['hero.png'],'widgets_values_named':{'image':'hero.png'}},
            {'id':7,'type':'MiniMaxH3DirectorSettings','widgets_values_named':{'steps':25,'width':1344}}],
            'links':[[1,6,0,5,0,'IMAGE']]}

    def export(self):
        return self.manager.export_lightweight_project_data(self.timeline,workflow=self.workflow,master_node_id=5)

    def test_editable_json_has_one_timeline_and_preserves_graph(self):
        data=self.export();text=json.dumps(data)
        self.assertNotIn('stale duplicate',text)
        self.assertNotIn('cache_report',text);self.assertNotIn('draft_updated_at',text)
        self.assertNotIn('saved_generation',text);self.assertNotIn('server_cache_manifest',data)
        self.assertEqual(data['workflow']['links'],self.workflow['links'])
        self.assertEqual(data['reference_catalog'][0]['id'],'image_1')
        data['timeline']['clips'][0]['prompt']='AI edited'
        data['timeline']['clips'].extend([{'prompt':'New clip A','duration':8},
            {'id':'agent_new_clip','prompt':'New clip B','duration':6}])
        restored=self.manager.import_lightweight_project_data(data)
        self.assertEqual(len(set(c['id'] for c in restored['clips'])),3)
        self.assertEqual(restored['clips'][2]['id'],'agent_new_clip')
        self.assertFalse(restored['clips'][1]['validated'])
        self.assertEqual(restored['clips'][0]['seed'],'18446744073709551615')
        graph=prepare_workflow(data['workflow'],5,restored)
        self.assertEqual(json.loads(graph['nodes'][0]['widgets_values_named']['timeline_data'])['clips'][0]['prompt'],'AI edited')
        self.assertEqual(graph['nodes'][2],self.workflow['nodes'][2])

    def test_duplicate_ids_rejected_and_upload_cannot_invent_cached_results(self):
        data=self.export();data['timeline']['clips'].append(copy.deepcopy(data['timeline']['clips'][0]))
        with self.assertRaisesRegex(ValueError,'Duplicate clip ID'):self.manager.import_lightweight_project_data(data)
        data=self.export();data['result_bindings']={'one':{'generation':'not-present','fingerprint':'forged'}}
        restored=self.manager.import_lightweight_project_data(data)
        self.assertTrue(restored['clips'][0]['validated'])
        self.assertEqual(restored['clips'][0]['validated_generation'],'not-present')
        self.assertFalse(self.manager.result_availability().get('one',{}).get('can_approve',False))
        self.assertEqual(self.manager._load_manifest()['clips'],{})

    def test_named_references_resolve_against_current_pool_not_old_slot_ids(self):
        self.timeline['clips'][0]['ref_ids']=['image_1']
        data=self.export()
        self.assertEqual(data['timeline']['clips'][0]['ref_names'],['Hero'])
        self.assertNotIn('ref_ids',data['timeline']['clips'][0])
        result=self.manager.import_lightweight_project_data(data,[{'id':'p3_image_4','name':'Hero'}])
        self.assertEqual(result['clips'][0]['ref_ids'],['p3_image_4'])
        with self.assertRaisesRegex(ValueError,'missing or ambiguous'):
            self.manager.import_lightweight_project_data(data,[])

    def test_generated_results_bundle_round_trip_is_isolated(self):
        from unittest.mock import patch
        frames=torch.zeros((2,4,4,3));audio={'waveform':torch.zeros((1,2,2000)),'sample_rate':48000}
        self.manager.store_clip_results('one','fingerprint',{'samples':torch.zeros((1,4,2,2))},audio,frames)
        before=self.manager._load_manifest();(self.input/'hero.png').write_bytes(b'input-media')
        archive=self.root/'bundle.mmxproj'
        write_bundle(self.manager,self.timeline,self.workflow,5,str(self.input),archive,include_media=True,include_results=True)
        with zipfile.ZipFile(archive) as z:
            self.assertTrue(any(name.endswith('_latent.pt') for name in z.namelist()))
            self.assertTrue(any(name.endswith('_frames.pt') for name in z.namelist()))
            self.assertTrue(any(name.startswith('assets/') for name in z.namelist()))
        with patch('core.cache_manager.get_cache_root_dir',return_value=str(self.root/'cache')):
            result=read_bundle(archive,str(self.input))
            manager=ProjectCacheManager(result['timeline']['project_id'])
            self.assertTrue(torch.equal(manager.load_clip_frames('one'),frames))
            self.assertIsNotNone(manager.load_clip_latent('one'))
            self.assertEqual(result['restored_results'],1)
            self.assertNotEqual(manager.project_id,self.manager.project_id)
        self.assertEqual(self.manager._load_manifest(),before)
        filename=result['workflow']['nodes'][1]['widgets_values'][0]
        self.assertEqual((self.input/filename).read_bytes(),b'input-media')

    def test_archive_traversal_is_rejected(self):
        archive=self.root/'bad.zip'
        with zipfile.ZipFile(archive,'w') as z:z.writestr('../escape','bad')
        with self.assertRaisesRegex(ValueError,'Unsafe'):read_bundle(archive,str(self.input))


if __name__=='__main__':unittest.main()
