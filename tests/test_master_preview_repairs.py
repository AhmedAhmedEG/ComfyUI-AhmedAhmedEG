"""Regressions for the 2026-10-18 execution and preview review."""
import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from tests import test_runtime_contracts as runtime
from core.cache_manager import ProjectCacheManager
from core.preview import create_preview_plan
from core.timeline_input import merge_authored_timeline

torch = runtime.torch


@contextmanager
def master():
    case = runtime.RuntimeContracts()
    case.setUp()
    try:
        yield case
    finally:
        case.doCleanups()


class MasterPreviewRepairs(unittest.TestCase):
    def test_unused_pool_assets_are_not_hashed_or_prepared_on_startup(self):
        with master() as case:
            from core.reference_cache import ReferenceEncodeCache
            refs={'refs':[{'id':'unused','type':'video','data':torch.zeros((5,16,16,3))}]}
            with patch.object(ReferenceEncodeCache,'source_key',side_effect=AssertionError('Unused source was scanned')):
                case.execute([{'id':'one','type':'T2V','duration':1}],ref_pack=refs)

    def test_first_pass_approval_is_bound_to_the_reviewed_draft(self):
        with master() as case:
            options={'enabled':True,'mode':'refine','confirm_first_pass':True,'skip_fl2v':False}
            state=json.loads(case.execute([{'id':'one','type':'T2V','duration':1}],refine=options)[-1])
            manager=ProjectCacheManager('regression',case.temp.name)
            self.assertTrue(manager.result_availability()['one']['refine_pending'])
            state['clips'][0].update(refine_approved=True,refine_approved_generation='obsolete')
            with patch('nodes.node_director.apply_refine_pass') as refine:
                result=case.execute(timeline_data=json.dumps(state),refine=options)
            refine.assert_not_called()
            self.assertFalse(json.loads(result[-1])['clips'][0]['refine_approved'])

    def test_latest_output_skips_loading_unneeded_approved_predecessors(self):
        with master() as case:
            shots=[{'id':name,'type':'T2V','duration':1,'continuity':False} for name in ['one','two','three']]
            result=case.execute(shots,config={'project_id':'regression','run_mode':'full_batch','decoded_output':'latest'})
            state=json.loads(result[-1])
            for shot in state['clips']:shot['validated']=True
            original=ProjectCacheManager.load_clip_latent;loaded=[]
            def load(manager,cid):loaded.append(cid);return original(manager,cid)
            with patch.object(ProjectCacheManager,'load_clip_latent',load):
                replay=case.execute(timeline_data=json.dumps(state),config={'project_id':'regression','run_mode':'full_batch','decoded_output':'latest'})
            self.assertEqual(loaded,['three'])
            replay_clips=json.loads(replay[-1])['clips']
            self.assertTrue(all(c['cache_report']['stats']['Saved clip']['hit']==1 for c in replay_clips))
            self.assertEqual([{k:v for k,v in c.items() if k!='cache_report'} for c in replay_clips],
                             [{k:v for k,v in c.items() if k!='cache_report'} for c in state['clips']])
            self.assertEqual(replay[0].shape,result[0].shape)

    def test_approval_cannot_silently_follow_replaced_generation(self):
        with master() as case:
            state=json.loads(case.execute([{'id':'one','type':'T2V','duration':1}])[-1])
            state['clips'][0].update(validated=True,validated_generation='obsolete')
            case.sampling_calls.clear()
            with self.assertRaisesRegex(ValueError,'replaced or removed'):
                case.execute(timeline_data=json.dumps(state))
            self.assertEqual(case.sampling_calls,[])

    def test_unvalidated_dependents_deleted_before_parent_sampling_even_if_sampling_fails(self):
        with master() as case:
            shots=[{'id':'one','type':'T2V','duration':1,'continuity':False},
                   {'id':'two','type':'T2V','duration':1,'continuity_mode':'Motion Context (Chained)',
                    'context_length':5,'audio_context_length':5},
                   {'id':'three','type':'T2V','duration':1,'continuity':False}]
            state=json.loads(case.execute(shots)[-1])
            for shot in state['clips']: shot['validated']=False
            state['clips'][0]['prompt']='changed parent prompt'
            manager=ProjectCacheManager('regression',case.temp.name)
            old=manager._manifest['clips']['two']['generation']
            def fail(*args, **kwargs):
                current=ProjectCacheManager('regression',case.temp.name)
                self.assertNotIn('two', current._manifest['clips'])
                self.assertIn('one', current._manifest['clips'])
                self.assertIn('three', current._manifest['clips'])
                self.assertFalse(list(Path(manager.project_dir).glob('*'+old+'*.pt')))
                raise RuntimeError('Intentional sampler failure')
            with patch('comfy.sample.sample', side_effect=fail):
                with self.assertRaisesRegex(RuntimeError,'Intentional sampler failure'):
                    case.execute(timeline_data=json.dumps(state),
                        config={'project_id':'regression','run_mode':'clip_by_clip'})

    def test_replacing_parent_removes_dependent_cache_and_approval_before_reuse(self):
        with master() as case:
            shots=[{'id':'one','type':'T2V','duration':1,'continuity':False},
                   {'id':'two','type':'T2V','duration':1,'continuity_mode':'Motion Context (Chained)',
                    'context_length':5,'audio_context_length':5}]
            state=json.loads(case.execute(shots)[-1])
            manager=ProjectCacheManager('regression',case.temp.name)
            old=manager._manifest['clips']['two']['generation']
            state['clips'][1]['validated']=True
            state['clips'][0]['prompt']='changed parent prompt'
            case.sampling_calls.clear()
            result=case.execute(timeline_data=json.dumps(state))
            self.assertEqual(len(case.sampling_calls),2,'The old approved successor must not be reused after its parent changes')
            self.assertFalse(json.loads(result[-1])['clips'][1]['validated'])
            self.assertNotEqual(ProjectCacheManager('regression',case.temp.name)._manifest['clips']['two']['generation'],old)
            self.assertFalse(list(Path(manager.project_dir).glob('*'+old+'*.pt')))

    def test_paired_audio_reaches_native_numbered_slots(self):
        with master() as case:
            audio = {'waveform': torch.ones((1, 2, 32000)), 'sample_rate': 32000}
            refs = [{'id': 'v'+str(i), 'type': 'video',
                     'data': torch.ones((22, 32, 32, 3)), 'audio': audio} for i in (1, 2)]
            case.execute([{'id': 'one', 'type': 'REF2VA', 'duration': 1,
                           'ref_ids': ['v1', 'v2']}], ref_pack={'refs': refs})
            args = next(kw for name, kw in case.native_calls if name == 'MiniMaxH3ReferenceToVideo')
            self.assertEqual(set(args['ref_video_audios']), {'ref_video_audio_1', 'ref_video_audio_2'})
            self.assertEqual(set(args['ref_videos']), {'ref_video_1', 'ref_video_2'})

    def test_first_clip_consumes_external_checkpoint(self):
        with master() as case:
            checkpoint = {'latent': None, 'frames': torch.ones((22, 32, 32, 3)),
                          'audio': {'waveform': torch.ones((1, 2, 32000)), 'sample_rate': 32000}}
            result = case.execute([{'id': 'one', 'type': 'I2VA', 'duration': 1,
                'continuity': True, 'continuity_mode': 'Motion Context (Chained)'}], latent_checkpoint=checkpoint)
            self.assertEqual(len(case.sampling_calls), 1)
            self.assertTrue(case.sampling_calls[0]['positive'][0][1]['minimax_keyframes'])
            self.assertEqual(json.loads(result[8])['shots'][0]['continuity_source'],'decoded_fallback')
            self.assertEqual(json.loads(result[8])['shots'][0]['action'], 'generated')
            manager = ProjectCacheManager('regression', case.temp.name)
            self.assertEqual(manager._manifest['clips']['one']['previous_trim'], 0)

    def test_conditioning_only_does_not_hide_completed_preview(self):
        with master() as case:
            state = json.loads(case.execute()[-1])
            self.assertTrue(create_preview_plan(state, base_dir=case.temp.name)['found'])
            case.sampling_calls.clear()
            case.execute(timeline_data=json.dumps(state), generation_mode='Conditioning only')
            self.assertEqual(case.sampling_calls, [])
            self.assertTrue(create_preview_plan(state, base_dir=case.temp.name)['found'])

    def test_reused_first_pass_stays_reviewable_and_historical(self):
        with master() as case:
            options = {'enabled': True, 'mode': 'refine', 'confirm_first_pass': True, 'skip_fl2v': False}
            state = json.loads(case.execute(refine=options)[-1])
            manager = ProjectCacheManager('regression', case.temp.name)
            draft = manager._manifest['first_pass']['one']['generation']
            case.sampling_calls.clear()
            case.execute(timeline_data=json.dumps(state), refine=options)
            self.assertEqual(case.sampling_calls, [])
            self.assertTrue(create_preview_plan(state, base_dir=case.temp.name, stream='first_pass')['found'])
            state['clips'][0]['refine_approved'] = True
            with patch('nodes.node_director.apply_refine_pass', side_effect=lambda **kw: kw['latent_dict']):
                case.execute(timeline_data=json.dumps(state), refine=options)
            manager = ProjectCacheManager('regression', case.temp.name)
            take = manager._manifest['clips']['one']['generation']
            old = manager.load_first_pass('one')
            manager.store_first_pass('one', 'unrelated-new-draft', old['latent'],
                manager.load_clip_frames('one'), manager.load_clip_audio('one'))
            # The current draft remains reviewable; historical take selection is removed.
            info = create_preview_plan(state, base_dir=case.temp.name, stream='first_pass')
            self.assertTrue(info['found'])
            with self.assertRaises(ValueError):
                create_preview_plan(state, 'take', case.temp.name)
            manager.update_clip_metadata('one', {'first_pass': None})
            self.assertFalse(create_preview_plan(state, base_dir=case.temp.name, stream='first_pass')['found'])

    def test_approved_recovery_uses_saved_color_not_current_controls(self):
        with master() as case:
            clip = {'id': 'one', 'type': 'T2VA', 'duration': 1, 'color': {'exposure': 1}}
            with patch('nodes.node_director.decode_video_latent', return_value=torch.ones((22,32,32,3))*.25):
                case.execute([clip])
                manager = ProjectCacheManager('regression', case.temp.name)
                expected = manager.load_clip_frames('one').clone()
                generation = manager._manifest['clips']['one']['generation']
                os.unlink(manager.get_clip_frames_path('one'))
                result = case.execute([{**clip, 'validated': True, 'color': {'exposure': 0}}])
                self.assertTrue(torch.equal(result[0], expected))
                self.assertEqual(ProjectCacheManager('regression', case.temp.name)._manifest['clips']['one']['generation'], generation)

    def test_missing_postprocessed_final_frames_do_not_mutate_approved_take(self):
        with master() as case:
            case.execute()
            manager = ProjectCacheManager('regression', case.temp.name)
            manager.update_clip_metadata('one', {'media_recovery': {'requires_final_media': True}})
            os.unlink(manager.get_clip_frames_path('one'))
            case.sampling_calls.clear()
            with self.assertRaisesRegex(ValueError, 'final frames are missing'):
                case.execute([{'id': 'one', 'type': 'T2VA', 'validated': True}])
            self.assertEqual(case.sampling_calls, [])
            self.assertFalse(os.path.exists(manager.get_clip_frames_path('one')))

    def test_external_prompt_change_invalidates_dependent_chain_only(self):
        clips = [{'id': key, 'prompt': 'old', 'validated': True,
                  'continuity_mode': 'Motion Context (Chained)' if key == 'two' else 'Independent (No Continuity)'}
                 for key in ('one', 'two', 'three')]
        incoming = json.loads(json.dumps(clips))
        incoming[0]['prompt'] = 'new'
        result = merge_authored_timeline({'clips': clips}, {'clips': incoming})
        self.assertEqual([c['validated'] for c in result['clips']], [False, False, True])
