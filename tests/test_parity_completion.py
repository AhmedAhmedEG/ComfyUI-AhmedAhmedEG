import io,json,tempfile,unittest,uuid,zipfile,hashlib
from pathlib import Path
from unittest.mock import patch
from tests.mock_torch import setup_mock_torch_if_needed
torch=setup_mock_torch_if_needed()
from core.forge_jobs import DraftJob,DraftCancelled,start_job,cancel_job,finish_job
from core.refine_controls import next_refine_seed
from core.forge_mapping import mapped_prompt,prompt_digest
from core.project_conversion import read_conversion,convert_project


class Completion(unittest.TestCase):
    def test_seed_advancement_is_uint64_and_does_not_touch_clip(self):
        self.assertEqual(next_refine_seed('18446744073709551615','increment'),'0')
        self.assertEqual(next_refine_seed('0','decrement'),'18446744073709551615')
        self.assertEqual(next_refine_seed('99','fixed'),'99')

    def test_cancel_job_sets_worker_token_and_closes_bound_stream(self):
        key,job=start_job(str(uuid.uuid4()));stream=io.BytesIO(b'{}');job.bind_response(stream)
        self.assertTrue(cancel_job(key));self.assertTrue(stream.closed)
        with self.assertRaises(DraftCancelled):job.check()
        finish_job(key);self.assertFalse(cancel_job(key))

    def test_verified_mapping_follows_ids_and_rejects_removed_reference(self):
        prompt='Follow <Picture 1>.'
        clip={'prompt':prompt,'forge_prompt_digest':prompt_digest(prompt),'forge_reference_snapshot':[{'id':'hero','label':'<Picture 1>'}]}
        self.assertEqual(mapped_prompt(clip,[{'id':'hero','label':'<Picture 2>'}]),'Follow <Picture 2>.')
        with self.assertRaises(ValueError):mapped_prompt(clip,[])
        self.assertEqual(mapped_prompt({**clip,'prompt':'Manually reviewed'},[]),'Manually reviewed')

    def test_download_verifies_hash_and_cleans_partial(self):
        from core import model_downloads as downloads
        content=b'valid model';digest=hashlib.sha256(content).hexdigest()
        with tempfile.TemporaryDirectory() as root,patch.object(downloads,'EXPECTED_BYTES',len(content)),patch.object(downloads,'MODEL_SHA256',digest),patch('urllib.request.urlopen',return_value=io.BytesIO(content)):
            name=downloads.ensure_h3_upscaler(root);self.assertEqual((Path(root)/name).read_bytes(),content)
        with tempfile.TemporaryDirectory() as root,patch.object(downloads,'EXPECTED_BYTES',len(content)),patch.object(downloads,'MODEL_SHA256','0'*64),patch('urllib.request.urlopen',return_value=io.BytesIO(content)):
            with self.assertRaises(ValueError):downloads.ensure_h3_upscaler(root)
            self.assertEqual(list(Path(root).iterdir()),[])

    def test_raw_tritant_archive_imports_real_native_latent_without_pickle(self):
        video=torch.ones((1,24,2,2,2));audio=torch.ones((1,32,2,8));raw=video.numpy().tobytes()+audio.numpy().tobytes()
        vs={'offset':0,'nbytes':video.numel()*4,'shape':list(video.shape),'dtype':'float32'}
        aus={'offset':vs['nbytes'],'nbytes':audio.numel()*4,'shape':list(audio.shape),'dtype':'float32'}
        archive=io.BytesIO()
        project={'project':{'extender':{'generation_mode':'ref2va','clips_json':{'clips':[{'id':'original','duration':5/24,'prompt':'p'}]},'refs_json':{'refs':[None]*9}}}}
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('project.json',json.dumps(project));z.writestr('cache/chain.json',json.dumps({'segments':[{'video':vs,'audio':aus,'validated':True,'trim_frames':0}]}));z.writestr('cache/chain.h3cache',raw)
        with tempfile.TemporaryDirectory() as root:
            state,report=read_conversion(archive.getvalue(),root,restore_cache=True,cache_root=root)
            self.assertTrue(report['cache_imported']);self.assertTrue(state['clips'][0]['validated'])
            from core.cache_manager import ProjectCacheManager
            from core.continuity import extract_streams_from_av_latent
            restored=ProjectCacheManager(state['project_id'],root).load_clip_latent(state['clips'][0]['id'])
            v,a=extract_streams_from_av_latent(restored);self.assertTrue(torch.equal(v,video));self.assertTrue(torch.equal(a,audio))

    def test_imported_sampler_and_model_contracts_are_explicit(self):
        data={'global':{'taskType':'t2v'},'widgets':{'steps':4,'sampler':'euler','cfg':1},'model_bindings':{'shot':{'filename':'h3.safetensors'}},'segments':[{'prompt':'walk','duration':2,'model_override':'shot'}]}
        state,report=convert_project(data,'aimixer')
        self.assertEqual(report['bindings']['config']['steps'],4);self.assertEqual(state['clips'][0]['model_override'],'shot')


    def test_archive_id_only_reference_and_endpoint_paths_are_resolved(self):
        from core.foreign_archives import archive_metadata
        blob=io.BytesIO()
        with zipfile.ZipFile(blob,'w') as z:
            for filename in ['refs/ref_1.png','fl2va/clip_1_first.png','local_refs/media/movie.bin']:z.writestr(filename,b'fixture')
        with zipfile.ZipFile(blob) as z:
            data={'project':{'extender':{'refs_json':{'refs':[{'id':'face'},None]},'clips_json':{'clips':[{'first_frame':{'id':'start'},'local_refs':{'videos':[{'media':{'id':'movie'}}]}}]}}}}
            bound=archive_metadata(z,data,'project.json')['project']['extender']
        self.assertEqual(bound['refs_json']['refs'][0]['filename'],'refs/ref_1.png')
        self.assertEqual(bound['clips_json']['clips'][0]['first_frame']['filename'],'fl2va/clip_1_first.png')
        self.assertEqual(bound['clips_json']['clips'][0]['local_refs']['videos'][0]['media']['filename'],'local_refs/media/movie.bin')

    def test_imported_video_source_and_legacy_reference_use_real_filename(self):
        state,_=convert_project({'global':{'taskType':'v2v'},'video':{'videoFile':'source.mp4'},'segments':[{'start':48,'length':48,'referenceVideo':{'videoFile':'motion.mp4'}}]},'aimixer')
        shot=state['clips'][0];pool={r['id']:r for r in state['references']}
        self.assertEqual(pool[shot['source']['ref_id']]['filename'],'source.mp4')
        self.assertEqual(shot['source_start'],2);self.assertEqual(shot['source_end'],4)
        self.assertEqual(pool[shot['ref_ids'][0]]['filename'],'motion.mp4')

    def test_global_planner_workspace_reserve_is_enforced(self):
        import sys,types
        from unittest.mock import patch
        minimax=types.ModuleType('comfy.ldm.minimax.model')
        minimax.FRAME_PER_TOKEN=[1,4,3,4,5];minimax.FRAME_RESCALE=1;minimax.PackedLayout=object
        common=types.ModuleType('comfy.ldm.common_dit');common.pad_to_patch_size=lambda x,*a:x
        with patch.dict(sys.modules,{'comfy.ldm.minimax.model':minimax,'comfy.ldm.common_dit':common,'comfy.utils':types.ModuleType('comfy.utils'),'comfy.model_management':types.ModuleType('comfy.model_management')}):
            from core.vendor.dasiwa.h3_tiled_sampling import plan_tiles
            with self.assertRaises(MemoryError):plan_tiles((1,24,2,2,2),32,32,10**9,workspace_reserve_pct=100)
            plan=plan_tiles((1,24,2,2,2),32,32,10**9,workspace_reserve_pct=35)
        self.assertIn('35% headroom',plan['explanation'])

    def test_refine_rejects_unknown_seed_advancement_before_loading(self):
        from nodes.node_refine import MiniMaxH3DirectorRefine
        with self.assertRaises(ValueError):MiniMaxH3DirectorRefine().build_config('refine',3,.4,64,64,False,2,seed_after_generate='wrong')

    def test_tritant_clip_zero_and_color_conversion_keep_existing_owners(self):
        state,_=convert_project({'extender':{'clips_json':{'continue_existing_video':{'filename':'video.mp4','duration':2},'clips':[{'id':'shot','duration':1,'color_adjustment':{'brightness':125,'contrast':120,'saturation':80}}]}}},'tritant')
        self.assertTrue(state['clips'][0]['locked']);self.assertEqual(state['clips'][0]['source_end'],2)
        from core.references import edit_images
        pixels=torch.tensor([[[[.2,.4,.6]]]])
        color=state['clips'][1]['color'];gray=.2*.213+.4*.715+.6*.072
        expected=((gray+(pixels-gray)*.8-.5)*1.2+.5)*1.25
        self.assertTrue(torch.allclose(edit_images(pixels,color),expected))

    def test_remote_writer_streams_draft_and_requests_ollama_unload(self):
        from core.forge import draft_prompts
        row={'message':{'content':json.dumps({'shots':[{'prompt':'A red boat moves.','duration':1,'type':'T2VA'}]})}}
        requests=[]
        def response(request,**kwargs):
            requests.append(json.loads(request.data));return io.BytesIO((json.dumps(row)+'\n').encode())
        state={'clips':[{'id':'shot','type':'T2VA','duration':1,'prompt':'before'}]}
        with patch('urllib.request.urlopen',side_effect=response):
            result=draft_prompts(state,'write',model='fixture',job=DraftJob())
        self.assertEqual(result['shots'][0]['prompt'],'A red boat moves.')
        self.assertTrue(requests[0]['stream']);self.assertEqual(requests[0]['keep_alive'],0)

    def test_remote_cancelled_stream_never_returns_partial_draft(self):
        from core.forge import draft_prompts
        job=DraftJob()
        def response(*args,**kwargs):
            job.cancel();return io.BytesIO(b'')
        with patch('urllib.request.urlopen',side_effect=response):
            with self.assertRaises(DraftCancelled):draft_prompts({'clips':[]},'write',model='fixture',job=job)
