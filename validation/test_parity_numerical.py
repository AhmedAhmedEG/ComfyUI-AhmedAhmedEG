"""Real tensor and codec checks for the newly exposed parity paths."""
import tempfile,types,sys,unittest
from unittest.mock import patch
from pathlib import Path
import torch
import av
from core.asset_editor import prepare_asset
from core.cache_manager import ProjectCacheManager
from core.preview import create_preview_plan,encode_preview
from nodes.node_frame_interpolation import MiniMaxH3FrameInterpolation

class ParityNumerical(unittest.TestCase):
    def test_shared_pixel_fit_fill_and_lanczos_preserve_aspect(self):
        from core.pixel_resize import resize_pixels
        images=torch.ones((2,32,64,3))
        for method in ('bicubic','lanczos'):
            fit=resize_pixels(images,64,64,'Letterbox (Fit)',method)
            fill=resize_pixels(images,64,64,'Center Crop (Fill)',method)
            self.assertEqual(tuple(fit.shape),(2,64,64,3))
            self.assertEqual(float(fit[:,:16].abs().sum()),0)
            self.assertAlmostEqual(float(fit[:,16:48].mean()),1,delta=.001)
            self.assertAlmostEqual(float(fill.mean()),1,delta=.001)

    def test_project_export_encodes_cached_pack_sources_at_enclosing_canvas(self):
        from validation import test_media_codec as codec
        codec.MediaCodec.setUp(self)
        from nodes.node_project_video import MiniMaxH3ProjectVideo
        api=types.ModuleType('comfy_api.latest');api.InputImpl=types.SimpleNamespace(VideoFromFile=lambda path:path)
        root=Path(self.temp.name);manager=ProjectCacheManager('export',str(root/'cache'))
        audio={'waveform':torch.zeros((1,2,10000)),'sample_rate':48000}
        for cid,shape,color in [('one',(5,32,64,3),.2),('two',(5,96,32,3),.8)]:
            manager.store_clip_results(cid,cid,None,audio,torch.full(shape,color))
        import json
        state={'project_id':'export','audio_fade_ms':0,'audio_gain_match':False,'clips':[{'id':'one','locked':True,'source':{'ref_id':'pack_video'}},{'id':'two'}]}
        with patch.dict(sys.modules,{'comfy_api.latest':api,'comfy_api':types.ModuleType('comfy_api')}),patch('nodes.node_project_video.ProjectCacheManager',return_value=manager):
            result=MiniMaxH3ProjectVideo().export(json.dumps(state),'export',filename_prefix='export')
        with av.open(result['result'][0]) as container:
            frames=list(container.decode(video=0));self.assertEqual(len(frames),10)
            self.assertEqual((frames[0].height,frames[0].width),(96,64))
            self.assertLess(float(frames[0].to_ndarray(format='rgb24').mean()),float(frames[-1].to_ndarray(format='rgb24').mean()))

    def test_staged_and_intermediate_streams_encode_their_actual_frames(self):
        with tempfile.TemporaryDirectory() as root:
            manager=ProjectCacheManager('parity',root)
            audio={'waveform':torch.zeros((1,2,10000)),'sample_rate':48000}
            first=torch.full((5,32,64,3),.2);second=torch.full((5,64,96,3),.8)
            manager.store_first_pass('one','fp',{'samples':torch.ones((1,24,1,2,4))},first,audio)
            self.assertIsNone(manager.load_first_pass('one','changed'))
            self.assertTrue(torch.equal(manager.load_first_pass('one','fp')['latent']['samples'],torch.ones((1,24,1,2,4))))
            intermediate=manager.store_refine_pass('one',1,second,audio)
            manager.store_clip_results('one','final',None,audio,second)
            manager.update_clip_metadata('one',{'refine_passes':[intermediate]})
            state={'project_id':'parity','clips':[{'id':'one'}]}
            for stream,shape,pixel in [('first_pass',(32,64),.2),('pass:1',(64,96),.8)]:
                plan=create_preview_plan(state,base_dir=root,stream=stream)
                self.assertTrue(plan['found']);video=encode_preview('parity',plan['key'],root)
                with av.open(video) as container:
                    frames=list(container.decode(video=0));self.assertEqual(len(frames),5)
                    self.assertEqual((frames[0].height,frames[0].width),shape)
                    self.assertAlmostEqual(float(frames[0].to_ndarray(format='rgb24').mean()/255),pixel,delta=.03)

    def test_pack_trim_crop_grading_and_interpolation_use_real_pixels(self):
        frames=torch.linspace(0,1,48).view(48,1,1,1).expand(48,64,128,3).clone()
        sound={'waveform':torch.ones((1,2,96000)),'sample_rate':48000}
        row=prepare_asset({'id':'v','type':'video','data':frames,'audio':sound},{'start':.5,'end':1.5,'crop':{'x':0,'y':0,'width':.5,'height':1},'edits':{'exposure':1}})
        self.assertEqual(row['data'].shape,(24,64,64,3));self.assertGreater(float(row['data'].mean()),float(frames[12:36].mean()))
        self.assertEqual(row['audio']['waveform'].shape[-1],48000)
        output,audio,fps=MiniMaxH3FrameInterpolation().interpolate(row['data'],audio=row['audio'])
        self.assertEqual((output.shape[0],fps),(48,48));self.assertEqual(audio['waveform'].shape[-1],48000)
        self.assertTrue(torch.equal(output[0],row['data'][0]));self.assertTrue(torch.equal(output[-1],row['data'][-1]))

    def test_spike_guard_has_an_effect_and_zero_strength_is_identity(self):
        from core.vendor.dasiwa.h3_spike_guard import spike_guard,BURN_DIRECTION
        manager=types.SimpleNamespace(throw_exception_if_processing_interrupted=lambda:None,get_free_memory=lambda device:10**10)
        comfy=types.ModuleType('comfy');comfy.model_management=manager
        source=torch.randn((1,24,3,8,8),generator=torch.Generator().manual_seed(8))
        baseline=torch.nn.functional.interpolate(source.reshape(24,3,8,8),size=(16,16),mode='nearest').reshape(1,24,3,16,16)
        dirty=baseline.clone();direction=torch.tensor(BURN_DIRECTION).view(1,24,1,1)
        dirty[:,:,1,6:10,6:10]+=direction*50
        untouched,_=spike_guard(source,dirty.clone(),strength=0);self.assertTrue(torch.equal(untouched,dirty))
        with patch.dict(sys.modules,{'comfy':comfy,'comfy.model_management':manager}):
            repaired,report=spike_guard(source,dirty.clone())
        self.assertFalse(torch.equal(repaired,dirty));self.assertIn('repaired',report)
        self.assertLess(float((repaired-baseline).square().mean()),float((dirty-baseline).square().mean()))

if __name__=='__main__':unittest.main()
