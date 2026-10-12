"""Real CPU tensors and encoded previews for injected pack sources; no model weights."""
import tempfile
import unittest
import torch
import av
from core.source_media import source_range
from core.cache_manager import ProjectCacheManager
from core.preview import create_preview_plan, encode_preview


class PackSourceNumerical(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        self.frames=torch.arange(48.).reshape(48,1,1,1).expand(48,64,128,3)/48
        self.audio={'waveform':torch.arange(96000.).reshape(1,1,96000),'sample_rate':48000}
        self.pool={'video':{'type':'video','data':{'frames':self.frames,'fps':24,'audio':self.audio}}}

    def test_trim_uses_pack_pixels_audio_and_separate_input_budget(self):
        result=source_range({'source':{'ref_id':'video'},'source_start':.5,'source_end':1.5,
                             'video_input_resolution':{'mode':'short_edge','short_edge':32}}, {},256,128,ref_pool=self.pool)
        self.assertTrue(torch.equal(result['original_frames'],self.frames[12:36]))
        self.assertEqual(tuple(result['frames'].shape),(24,128,256,3))
        self.assertEqual(tuple(result['model_frames'].shape),(24,32,64,3))
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


if __name__=='__main__': unittest.main()
