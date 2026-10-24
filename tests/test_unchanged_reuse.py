import json
import unittest
from unittest.mock import patch

from tests.test_master_preview_repairs import master
from core.cache_manager import ProjectCacheManager,fingerprint_value


class UnchangedReuse(unittest.TestCase):
    def test_full_run_reuses_unapproved_parent_and_successor_without_deleting_results(self):
        with master() as case:
            shots=[{'id':'one','type':'T2V','duration':1,'seed':7},
                {'id':'two','type':'T2V','duration':1,'seed':8,'continuity_mode':'Motion Context (Chained)','context_length':5}]
            state=json.loads(case.execute(shots)[-1])
            before={cid:m['generation'] for cid,m in ProjectCacheManager('regression',case.temp.name)._manifest['clips'].items()}
            case.sampling_calls.clear()
            result=case.execute(timeline_data=json.dumps(state))
            self.assertEqual(case.sampling_calls,[])
            self.assertEqual(json.loads(result[8])['generated'],0)
            self.assertEqual(before,{cid:m['generation'] for cid,m in ProjectCacheManager('regression',case.temp.name)._manifest['clips'].items()})
            self.assertTrue(all(not c.get('validated') for c in json.loads(result[-1])['clips']))

    def test_next_clip_unchanged_finishes_without_generating_the_following_clip(self):
        with master() as case:
            shots=[{'id':'one','type':'T2V','duration':1,'seed':7},{'id':'two','type':'T2V','duration':1,'seed':8}]
            state=json.loads(case.execute(shots,config={'project_id':'regression','run_mode':'clip_by_clip'})[-1])
            case.sampling_calls.clear()
            case.execute(timeline_data=json.dumps(state),config={'project_id':'regression','run_mode':'clip_by_clip'})
            self.assertEqual(case.sampling_calls,[])
            self.assertNotIn('two',ProjectCacheManager('regression',case.temp.name)._manifest['clips'])

    def test_changed_seed_or_sampling_settings_regenerate(self):
        for change in ['seed','steps','color','redraw']:
            with self.subTest(change=change),master() as case:
                state=json.loads(case.execute([{'id':'one','type':'T2V','duration':1,'seed':7}])[-1])
                kwargs={}
                if change=='seed':state['clips'][0]['seed']='8'
                elif change=='steps':kwargs['steps']=9
                elif change=='color':state['clips'][0]['color']={'brightness':.1}
                else:state['clips'][0]['continuity_redraw']=.25
                case.sampling_calls.clear()
                case.execute(timeline_data=json.dumps(state),**kwargs)
                self.assertEqual(len(case.sampling_calls),1)

    def test_missing_saved_frames_does_not_silently_skip_generation(self):
        with master() as case:
            state=json.loads(case.execute([{'id':'one','type':'T2V','duration':1,'seed':7}])[-1])
            case.sampling_calls.clear()
            with patch.object(ProjectCacheManager,'load_clip_frames',return_value=None):
                case.execute(timeline_data=json.dumps(state))
            self.assertEqual(len(case.sampling_calls),1)

    def test_native_nested_av_identity_depends_on_contents(self):
        import torch
        class Nested:
            is_nested=True
            def __init__(self,value):self.value=value
            def unbind(self):return (self.value,torch.zeros(1))
        self.assertEqual(fingerprint_value(Nested(torch.ones(2))),fingerprint_value(Nested(torch.ones(2))))
        self.assertNotEqual(fingerprint_value(Nested(torch.ones(2))),fingerprint_value(Nested(torch.zeros(2))))


if __name__=='__main__':unittest.main()
