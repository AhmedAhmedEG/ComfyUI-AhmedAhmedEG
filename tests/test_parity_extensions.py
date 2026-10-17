import io,json,tempfile,types,sys,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from tests.mock_torch import setup_mock_torch_if_needed
torch=setup_mock_torch_if_needed()
from core.asset_editor import prepare_asset,prepare_pack
from core.project_conversion import convert_project,read_conversion
from core.timeline_input import merge_authored_timeline,groups_to_timeline
from core.cache_manager import ProjectCacheManager
from nodes.node_refmod_library import MiniMaxH3RefModLibrary
from nodes.node_frame_interpolation import MiniMaxH3FrameInterpolation
from nodes.node_project_video import MiniMaxH3ProjectVideo


class ParityExtensions(unittest.TestCase):
    def test_asset_crop_trim_and_audio_pair_follow_pack_settings(self):
        frames=torch.ones((48,64,128,3))
        audio={'waveform':torch.ones((1,2,96000)),'sample_rate':48000}
        row={'id':'video_1','type':'video','data':frames,'audio':audio}
        result=prepare_asset(row,{'start':.5,'end':1.5,'crop':{'x':0,'y':0,'width':.5,'height':1},'media_mode':'both'})
        self.assertEqual(result['data'].shape,(24,64,64,3))
        self.assertEqual(result['audio']['waveform'].shape[-1],48000)
        self.assertEqual(frames.shape,(48,64,128,3),'Original asset must not be mutated')
        for mode,kind in [('frame','image'),('audio','audio'),('video','video')]:
            prepared=prepare_asset(row,{'media_mode':mode,'frame_time':.5})
            self.assertEqual(prepared['type'],kind);self.assertEqual(prepared['id'],'video_1')
        with self.assertRaises(ValueError):prepare_asset(row,{'start':3})

    def test_asset_settings_are_slot_owned_and_ids_remain_stable(self):
        row={'id':'p2_image_1','slot_id':'image_1','type':'image','data':torch.ones((1,64,96,3))}
        result=prepare_pack([row],{'assets':{'image_1':{'name':'Hero','role':'pose','description':'Running','scaling':'Divisible crop'}}})[0]
        self.assertEqual((result['id'],result['name'],result['role']),('p2_image_1','Hero','pose'))
        self.assertEqual(result['data'].shape,(1,64,96,3))

    def test_refmod_library_preserves_strength_description_and_unique_identity(self):
        library,=MiniMaxH3RefModLibrary().build(json.dumps([{'name':'Hero','description':'Lead character','strength':.4}]))
        row=library['refs'][0]
        self.assertEqual((row['strength'],row['description']),(.4,'Lead character'))
        again,=MiniMaxH3RefModLibrary().build(json.dumps([{'name':'Hero','strength':.8}]))
        self.assertEqual(row['id'],again['refs'][0]['id'])
        with self.assertRaises(ValueError):MiniMaxH3RefModLibrary().build('[{"name":"x","strength":-1}]')

    def test_builder_changes_authoring_but_preserves_master_execution_controls(self):
        external=groups_to_timeline([{'kind':'t2v','prompt':'builder text','duration_sec':2,'_builder_id':'7'}])
        old={'clips':[{'id':'group_7','prompt':'old','validated':True,'seed':'999','continuity_mode':'Latent Carry (Pinned)'}]}
        merged=merge_authored_timeline(old,external)
        self.assertEqual(merged['clips'][0]['prompt'],'builder text')
        self.assertFalse(merged['clips'][0]['validated']);self.assertEqual(merged['clips'][0]['seed'],'999')
        with self.assertRaises(ValueError):merge_authored_timeline(old,{'clips':[{'id':'a'},{'id':'a'}]})

    def test_frame_interpolation_preserves_duration_audio_and_endpoints(self):
        images=torch.cat([torch.zeros((1,32,32,3)),torch.ones((1,32,32,3))],dim=0)
        audio={'waveform':torch.ones((1,2,4000)),'sample_rate':48000}
        result,sound,fps=MiniMaxH3FrameInterpolation().interpolate(images,24,2,detect_cuts=False,audio=audio)
        self.assertEqual(result.shape[0],4);self.assertEqual(fps,48)
        self.assertEqual(sound['waveform'].shape[-1],4000)
        self.assertEqual(float(result[1].mean()),.5)
        self.assertEqual(float(result[0].mean()),0);self.assertEqual(float(result[-1].mean()),1)

    def test_upstream_conversion_is_stable_and_never_forges_approval(self):
        fixtures=[('dasiwa',{'dasiwa_minimax_h3_reference_pack':True,'model_mode':'REF2VA','items':[{'type':'image','value':'hero.png'}],'prompt':{'simple_prompt':'walk'}}),
            ('tritant',{'project':{'extender':{'generation_mode':'ref2va','clips_json':'{"clips":[{"prompt":"walk","duration":2,"validated":true}]}','references':[]}}}),
            ('aimixer',{'global':{'taskType':'t2v'},'segments':[{'prompt':'walk','duration':2}]})]
        for source,fixture in fixtures:
            with self.subTest(source=source):
                state,report=convert_project(fixture,source);again,_=convert_project(fixture,source)
                self.assertEqual(state['clips'][0]['id'],again['clips'][0]['id'])
                self.assertFalse(state['clips'][0]['validated']);self.assertFalse(report['cache_imported'])
        with self.assertRaises(ValueError):convert_project({'dasiwa_minimax_h3_reference_pack':True,'items':[{'type':'image','value':'../escape.png'}]},'dasiwa')

    def test_conversion_archive_rejects_traversal_before_writes(self):
        blob=io.BytesIO()
        with zipfile.ZipFile(blob,'w') as archive:
            archive.writestr('project.json','{"clips":[{"prompt":"walk"}]}')
            archive.writestr('../escape.png',b'bad')
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):read_conversion(blob.getvalue(),root)
            self.assertEqual(list(Path(root).iterdir()),[])

    def test_export_accepts_cached_pack_footage_and_enclosing_canvas(self):
        api=types.ModuleType('comfy_api.latest');api.InputImpl=types.SimpleNamespace(VideoFromFile=lambda path:path)
        with tempfile.TemporaryDirectory() as root,patch.dict(sys.modules,{'comfy_api.latest':api,'comfy_api':types.ModuleType('comfy_api')}):
            manager=ProjectCacheManager('parity',root);audio={'waveform':torch.ones((1,2,10000)),'sample_rate':48000}
            for cid,shape in [('one',(5,32,64,3)),('two',(5,96,32,3))]:manager.store_clip_results(cid,cid,None,audio,torch.ones(shape))
            sizes=[]
            def encode(frames,**kw):
                sizes.append(tuple(frames.shape[1:3]))
                return {'result':(None,str(Path(root)/f'{len(sizes)}.mp4')),'ui':{'video':[]}}
            with patch('nodes.node_project_video.ProjectCacheManager',return_value=manager),patch('nodes.node_project_video.FFMPEG_PATH','fixture'), \
                patch('nodes.node_project_video.MiniMaxH3VideoCombine.combine_video',side_effect=encode), \
                patch('nodes.node_project_video.subprocess.run',return_value=types.SimpleNamespace(returncode=0)), \
                patch('nodes.node_project_video.resolve_output_path',return_value=(str(Path(root)/'final.mp4'),'final.mp4','')):
                timeline={'clips':[{'id':'one','locked':True,'source':{'ref_id':'video'}},{'id':'two'}]}
                MiniMaxH3ProjectVideo().export(json.dumps(timeline),'parity')
                self.assertEqual(sizes,[(96,64),(96,64)])
                sizes.clear();MiniMaxH3ProjectVideo().export(json.dumps(timeline),'parity',selection='clip_ids',clip_ids='two')
                self.assertEqual(sizes,[(96,32)])
                with self.assertRaises(ValueError):MiniMaxH3ProjectVideo().export(json.dumps(timeline),'parity',selection='clip_ids',clip_ids='missing')

    def test_boundary_cleanup_is_version_gated_and_does_not_offload_diffusion(self):
        from core.memory_lifecycle import before_refine,between_clips
        active=types.SimpleNamespace(clone_base_uuid='model')
        known=types.SimpleNamespace(model=type('MiniMaxH3VideoVAE',(),{})(),clone_base_uuid='vae')
        other=types.SimpleNamespace(model=type('H3Diffusion',(),{})(),clone_base_uuid='model')
        calls=[];manager=types.SimpleNamespace(loaded_models=lambda:[known,other],unload_model_and_clones=lambda m,**kw:calls.append(m))
        with patch.dict(sys.modules,{'comfy.model_management':manager}),patch.object(sys.modules['comfy'],'model_management',manager):before_refine(active)
        self.assertEqual(calls,[known])
        with patch.dict(sys.modules,{'comfy.memory_management':types.SimpleNamespace(aimdo_enabled=False)}):between_clips()

if __name__=='__main__':unittest.main()
