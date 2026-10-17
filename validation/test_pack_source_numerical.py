"""Real CPU tensors and encoded previews for injected pack sources; no model weights."""
import tempfile
import unittest
import torch
import av
from core.source_media import source_range
from core.cache_manager import ProjectCacheManager
from core.preview import create_preview_plan, encode_preview


class PackSourceNumerical(unittest.TestCase):
    def test_live_full_preview_never_mixes_new_clip_with_old_future_take(self):
        from pathlib import Path
        import json
        with tempfile.TemporaryDirectory() as folder:
            manager=ProjectCacheManager('live_preview',folder)
            shots=[{'id':'one'},{'id':'two'}]
            state={'project_id':'live_preview','clips':shots}
            for shot in shots:
                manager.store_clip_results(shot['id'],'old',None,self.audio,self.frames)
            old_second=manager._manifest['clips']['two']['generation']
            empty=create_preview_plan(state,'full',folder,run_context={'clip_ids':[]})
            self.assertFalse(empty['found']);self.assertTrue(empty['run_active'])
            manager.store_clip_results('one','new',None,self.audio,self.frames[:24])
            context={'clip_ids':['one']}
            for scope in ('latest','full'):
                plan=create_preview_plan(state,scope,folder,run_context=context)
                self.assertEqual(plan['clip_ids'],['one'])
                self.assertTrue(plan['run_active'])
            media=encode_preview('live_preview',plan['key'],folder)
            with av.open(media) as video:
                self.assertEqual(sum(1 for _ in video.decode(video=0)),24,'Only the new one-second clip is encoded')
            saved=create_preview_plan(state,'take',folder,take_id=old_second,run_context=context)
            self.assertEqual(saved['clip_ids'],['two'],'Explicit Saved Take remains available')
            idle=create_preview_plan(state,'full',folder)
            self.assertEqual(idle['clip_count'],2,'Idle project browsing retains existing full-project behavior')

    def test_approval_and_fresh_run_results_preserve_latents_and_history(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            manager=ProjectCacheManager('approvals',folder)
            state={'project_id':'approvals','clips':[{'id':'one','validated':False}, {'id':'two','validated':True}]}
            for shot in state['clips']:
                manager.store_clip_results(shot['id'],'old',{'samples':torch.zeros((1,2))},self.audio,self.frames)
            old=manager._manifest['clips']['one']['generation']
            old_latent=manager.get_clip_latent_path('one')
            manager.begin_preview_run()
            self.assertEqual(create_preview_plan(state,'full',folder)['clip_ids'],['one','two'])
            manager.store_clip_results('one','new',{'samples':torch.ones((1,2))},self.audio,self.frames[:24])
            fresh=manager._manifest['clips']['one']['generation']
            self.assertNotEqual(old,fresh)
            self.assertTrue(Path(old_latent).is_file(),'Regeneration preserves saved-take history')
            self.assertEqual(create_preview_plan(state,'full',folder)['clip_ids'],['one','two'])
            state['clips'][0]['invalidated_generation']=fresh
            self.assertEqual(create_preview_plan(state,'full',folder)['clip_ids'],['one','two'])
            self.assertTrue(Path(manager.get_clip_latent_path('one')).is_file(),'Unapproval does not delete latent')
            self.assertTrue(create_preview_plan(state,'take',folder,take_id=fresh)['found'])
            manager.begin_preview_run()
            self.assertEqual(create_preview_plan(state,'full',folder)['clip_ids'],['one','two'])

    def test_pool_megapixels_reach_model_frames_for_graph_and_files(self):
        from core.asset_editor import prepare_pack
        from unittest.mock import patch
        frames=torch.linspace(0,1,3*384*640).reshape(3,384,640,1).expand(-1,-1,-1,3)
        rows=[{'id':'v','slot_id':'video_1','type':'video','data':frames}]
        for mp in (.05,.1):
            settings={'scaling':'Megapixels','megapixels':mp}
            graph=prepare_pack(rows,{'assets':{'video_1':settings}})[0]
            with patch('core.references.load_video',return_value=frames):
                file=prepare_pack([],{'files':[{'id':'file','type':'video','filename':'test.mp4',**settings}]},'input')[0]
            self.assertTrue(torch.equal(graph['data'],file['data']))
            h,w=graph['data'].shape[1:3]
            self.assertEqual(h%32,0);self.assertEqual(w%32,0)
            self.assertLessEqual(h*w,mp*1_000_000)
            source=source_range({'source':{'ref_id':'v'},'video_input_resolution':{'mode':'megapixels','megapixels':.001024}}, {},640,384,ref_pool={'v':graph})
            self.assertTrue(torch.equal(source['model_frames'],graph['data']),'Master must consume the pool result unchanged')
            self.assertEqual(tuple(source['frames'].shape[1:3]),(384,640),'Output canvas remains independent')
        self.assertEqual(tuple(frames.shape),(3,384,640,3))

    def test_pool_explicit_off_preserves_pixels_and_default_limits_video(self):
        from core.asset_editor import prepare_asset
        frames=torch.zeros((1,768,1344,3))
        row={'id':'video','type':'video','data':frames}
        default=prepare_asset(row,{})
        self.assertLessEqual(default['data'].shape[1]*default['data'].shape[2],500000)
        self.assertIs(prepare_asset(row,{'scaling':'Off'})['data'],frames)
        for mp in (float('nan'),0,2):
            with self.assertRaises(ValueError):prepare_asset(row,{'scaling':'Megapixels','megapixels':mp})

    def setUp(self):
        torch.set_num_threads(2)
        self.frames=torch.arange(48.).reshape(48,1,1,1).expand(48,64,128,3)/48
        self.audio={'waveform':torch.arange(96000.).reshape(1,1,96000),'sample_rate':48000}
        self.pool={'video':{'type':'video','data':{'frames':self.frames,'fps':24,'audio':self.audio}}}

    def test_trim_uses_pack_pixels_audio_without_second_clip_resize(self):
        result=source_range({'source':{'ref_id':'video'},'source_start':.5,'source_end':1.5,
                             'video_input_resolution':{'mode':'short_edge','short_edge':32}}, {},256,128,ref_pool=self.pool)
        self.assertTrue(torch.equal(result['original_frames'],self.frames[12:36]))
        self.assertEqual(tuple(result['frames'].shape),(24,128,256,3))
        self.assertEqual(tuple(result['model_frames'].shape),(24,64,128,3))
        self.assertTrue(torch.equal(result['audio']['waveform'],self.audio['waveform'][...,24000:72000]))
        self.assertEqual(result['end'],1.5)

    def test_no_filename_full_batch_and_fps_resampling(self):
        pool={'video':{'type':'video','data':{'frames':self.frames,'fps':48}}}
        result=source_range({'source':{'ref_id':'video'},'duration':5}, {},128,64,ref_pool=pool)
        self.assertEqual(result['frames'].shape[0],24)
        self.assertTrue(torch.equal(result['original_frames'],self.frames[::2]))
        self.assertEqual(torch.count_nonzero(result['audio']['waveform']).item(),0)
        with self.assertRaisesRegex(ValueError,'outside'):
            source_range({'source':{'ref_id':'video'},'source_start':99}, {},128,64,ref_pool=pool)
        with self.assertRaisesRegex(ValueError,'not in'):
            source_range({'source':{'ref_id':'missing'}}, {},128,64,ref_pool=pool)

    def test_public_ref_pack_normalizes_rate_and_preserves_paired_sound(self):
        import importlib.util
        from pathlib import Path
        spec=importlib.util.spec_from_file_location('pack_node',Path(__file__).resolve().parents[1]/'nodes/node_ref_pack.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        pack=module.MiniMaxH3RefPack().pack(video_1=self.frames,video_1_fps=48,video_1_audio=self.audio)[0]
        video=pack['refs'][0]
        self.assertTrue(torch.equal(video['data'],self.frames[::2]));self.assertIs(video['audio'],self.audio)

    def test_native_video_supplies_frames_fps_and_audio(self):
        import importlib.util
        from pathlib import Path
        from types import SimpleNamespace
        from fractions import Fraction
        spec=importlib.util.spec_from_file_location('native_pack_node',Path(__file__).resolve().parents[1]/'nodes/node_ref_pack.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        class NativeVideo:
            def get_components(inner):
                return SimpleNamespace(images=self.frames,audio=self.audio,frame_rate=Fraction(48))
        node=module.MiniMaxH3RefPack()
        self.assertEqual(node.INPUT_TYPES()['optional']['video_1'][0],'VIDEO,IMAGE')
        pack=node.pack(video_1=NativeVideo(),video_1_fps=12)[0]
        video=pack['refs'][0]
        self.assertTrue(torch.equal(video['data'],self.frames[::2]))
        self.assertIs(video['audio'],self.audio)
        override={'waveform':self.audio['waveform']*0,'sample_rate':48000}
        self.assertIs(node.pack(video_1=NativeVideo(),video_1_audio=override)[0]['refs'][0]['audio'],override)
        result=source_range({'source':{'ref_id':video['id']}}, {},128,64,ref_pool={video['id']:video})
        self.assertTrue(result['has_audio']);self.assertEqual(result['audio']['waveform'].shape[-1],48000)

    def test_pack_source_preview_survives_without_live_pack_or_fake_latent(self):
        with tempfile.TemporaryDirectory() as folder:
            manager=ProjectCacheManager('source_test',folder)
            state={'project_id':'source_test','clips':[{'id':'source','locked':True,'source':{'ref_id':'video'}}]}
            self.assertFalse(create_preview_plan(state,'full',folder)['found'],'Unexecuted pack source is not a completed clip')
            result=source_range({'source':{'ref_id':'video'},'duration':5}, {},128,64,ref_pool=self.pool)
            manager.store_clip_results('source','source',None,result['audio'],result['original_frames'])
            self.assertIsNone(manager.load_clip_latent('source'))
            plan=create_preview_plan(state,'full',folder)
            self.assertEqual(plan['clip_count'],1)
            path=encode_preview('source_test',plan['key'],folder)
            with av.open(path) as video:
                frames=list(video.decode(video=0))
                self.assertEqual(len(frames),48)
                self.assertEqual((frames[0].width,frames[0].height),(128,64))

    def test_approval_status_and_media_restore_use_real_files(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            manager=ProjectCacheManager('approval_test',folder)
            self.assertEqual(manager.result_availability(),{})
            manager.store_clip_results('one','take',{'samples':torch.zeros((1,24,2,4,8))})
            generation=manager._manifest['clips']['one']['generation']
            self.assertTrue(manager.result_availability()['one']['can_approve'])
            self.assertFalse(manager.result_availability()['one']['has_frames'])
            manager.restore_clip_media('one',self.frames,self.audio)
            self.assertEqual(manager._manifest['clips']['one']['generation'],generation)
            self.assertTrue(torch.equal(manager.load_clip_frames('one'),self.frames))
            Path(manager.get_clip_latent_path('one')).unlink()
            self.assertTrue(manager.result_availability()['one']['can_approve'],'Decoded take still exists')
            Path(manager.get_clip_frames_path('one')).unlink()
            self.assertFalse(manager.result_availability()['one']['can_approve'],'Audio alone cannot approve a clip')


if __name__=='__main__': unittest.main()
