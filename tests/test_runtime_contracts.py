"""Regression tests for native API contracts and execution/cache behavior."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from tests.mock_torch import setup_mock_torch_if_needed
torch = setup_mock_torch_if_needed()
from core.sampling import sample_latent, native_outputs
from core.cache_manager import ProjectCacheManager, fingerprint_value
from core.media_io import resolve_input_path
from core.audio_post import fit_audio_duration
from nodes.node_director import MiniMaxH3MasterDirector
from nodes.node_ref_pack import MiniMaxH3RefPack
from nodes.node_groups import MiniMaxH3DirectorGroupImageToVideo
from core.config import align_frame_count, video_latent_t, audio_latent_length


class NativeOutput:
    def __init__(self, *result):
        self.result = result


class SmallVAE:
    def encode(self, pixels):
        return torch.zeros((1, 24, video_latent_t(pixels.shape[0]), 2, 2))

    def decode(self, latent):
        if latent.ndim == 5:
            frames = 5 if latent.shape[2] <= 2 else (latent.shape[2] - 2) // 5 * 17 + 5
            return torch.zeros((frames, 32, 32, 3))
        return torch.zeros((1, latent.shape[-1] * 800, 2))


class RuntimeContracts(unittest.TestCase):
    def test_model_override_pack_does_not_request_unconnected_family_models(self):
        self.assertEqual(MiniMaxH3MasterDirector.check_lazy_status(
            model_pack={"custom":object()},timeline_data=json.dumps({"clips":[{"type":"T2VA","model_override":"custom"}]})),[])
    def test_mixed_override_pack_still_loads_unoverridden_model_families(self):
        clips=[{"type":"T2VA","model_override":"custom"},{"type":"REF2VA"},{"type":"T2VA"}]
        self.assertEqual(MiniMaxH3MasterDirector.check_lazy_status(model_pack={"custom":object()},
            timeline_data=json.dumps({"clips":clips})),["fl2va_model","ref2va_model"])
        self.assertEqual(MiniMaxH3MasterDirector.check_lazy_status(ref2va_model=object(), model_pack={"custom":object()},
            timeline_data=json.dumps({"clips":clips})),["fl2va_model"])
        with self.assertRaisesRegex(ValueError,"Unknown clip model override"):
            MiniMaxH3MasterDirector.check_lazy_status(model_pack={"other":object()},
                timeline_data=json.dumps({"clips":[{"type":"T2VA","model_override":"missing"}]}))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.node = MiniMaxH3MasterDirector()
        self.vae = SmallVAE()
        self.audio_vae = SmallVAE()
        self.audio_vae.audio_sample_rate = 32000
        self.clip = SimpleNamespace()
        self.model = SimpleNamespace(model_name="test-h3")
        self.native_calls = []
        self.sampling_calls = []
        self.patches = [
            patch("core.cache_manager.get_cache_root_dir", return_value=self.temp.name),
            patch("core.executor.get_native_h3_node", side_effect=self.native),
            patch("comfy.sample.fix_empty_latent_channels", side_effect=lambda m, s, *a: s),
            patch("comfy.sample.prepare_noise", side_effect=lambda s, seed, batch=None: s),
            patch("comfy.sample.prepare_empty_noise", side_effect=lambda s: s),
            patch("comfy.sample.sample", side_effect=self.strict_sample),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def strict_sample(self, model, noise, steps, cfg, sampler_name, scheduler,
                      positive, negative, latent_image, denoise=1., disable_noise=False,
                      start_step=None, last_step=None, force_full_denoise=False,
                      noise_mask=None, sigmas=None, callback=None, seed=None):
        self.assertNotIsInstance(noise, dict)
        self.assertNotIsInstance(latent_image, dict)
        self.sampling_calls.append({"model": model, "seed": seed, "steps": steps, "cfg": cfg, "sampler": sampler_name, "scheduler": scheduler,
            "samples": latent_image, "sigmas": sigmas, "noise_mask": noise_mask,
            "disable_noise": disable_noise, "start_step": start_step, "last_step": last_step})
        return latent_image

    def native(self, name):
        owner = self
        class Native:
            @classmethod
            def execute(cls, **kw):
                owner.native_calls.append((name, kw))
                if name == "MiniMaxH3AddGuide":
                    positive = [[emb, {**meta, "guide_used": True}] for emb, meta in kw["positive"]]
                    return NativeOutput(positive)
                frames = align_frame_count(kw["length"])
                samples = (torch.zeros((1, 24, video_latent_t(frames), 2, 2)),
                           torch.zeros((1, 32, 2, audio_latent_length(frames))))
                return NativeOutput([[torch.zeros((1, 2, 5120)), {}]], {"samples": samples})
        return Native

    def execute(self, clips=None, **kwargs):
        options = {"model": self.model, "video_vae": self.vae, "audio_vae": self.audio_vae,
            "clip": self.clip, "config": {"project_id": "regression", "run_mode": "full_batch"},
            "timeline_data": json.dumps({"clips": clips or [{"id": "one", "type": "T2VA", "duration": 1., "prompt": "walk"}]})}
        options.update(kwargs)
        return self.node.execute(**options)

    def test_approved_take_needs_no_live_reference_or_sampling_model(self):
        image = {"id":"opening","type":"image","data":torch.ones((1,32,32,3))}
        self.execute([{"id":"one","type":"I2V","duration":1,"ref_ids":["opening"]}],ref_pack={"refs":[image]})
        self.native_calls.clear(); self.sampling_calls.clear()
        result=self.execute([{"id":"one","type":"I2V","duration":1,"ref_ids":["opening"],"validated":True}],model=None)
        self.assertEqual(self.native_calls,[])
        self.assertEqual(self.sampling_calls,[])
        self.assertEqual(json.loads(result[8])["shots"][0]["action"],"cached")

    def test_cached_latent_carry_does_not_reapply_current_continuity(self):
        clips=[{"id":"one","type":"T2V","duration":2},
               {"id":"two","type":"T2V","duration":2,"continuity_mode":"Motion Context (Chained)","context_length":22}]
        self.execute(clips)
        for clip in clips: clip["validated"]=True
        clips[1]["continuity_mode"]="Latent Carry (Pinned)"
        self.native_calls.clear(); self.sampling_calls.clear()
        with patch('core.vendor.aimixer.director.h3_latent_continue.apply_latent_continue',side_effect=AssertionError('Accepted take must not be reconditioned')):
            self.execute(clips,model=None)
        self.assertEqual(self.native_calls,[])
        self.assertEqual(self.sampling_calls,[])

    def test_lazy_loading_matches_next_clip_and_approval(self):
        clips=[{"id":"a","type":"REF2VA","validated":True},
               {"id":"b","type":"T2V"},{"id":"c","type":"REF2VA"}]
        options={"timeline_data":json.dumps({"approval_control_version":1,"clips":clips})}
        self.assertEqual(self.node.check_lazy_status(**options,generation_mode="Next clip"),["fl2va_model"])
        self.assertEqual(self.node.check_lazy_status(**options,generation_mode="All clips"),["fl2va_model","ref2va_model"])
        for clip in clips: clip["validated"]=True
        self.assertEqual(self.node.check_lazy_status(timeline_data=json.dumps({"clips":clips})),[])

    def test_sampling_settings_and_shared_prompt_reach_execution(self):
        timeline={"project_id":"regression","shared_prompt":"cinematic","shared_prompt_policy":"append",
                  "audio_fade_ms":27,"audio_gain_match":False,
                  "clips":[{"id":"one","type":"T2V","duration":2,"seed":"1234","prompt":"walk"}]}
        from nodes import node_director
        with patch('nodes.node_director.concatenate_audio_clips', wraps=node_director.concatenate_audio_clips) as joins:
            result=self.execute(timeline_data=json.dumps(timeline),steps=17,cfg=2.5,sampler='euler',scheduler='normal')
        call=self.sampling_calls[0]
        self.assertEqual((call['steps'],call['cfg'],call['sampler'],call['scheduler'],call['seed']),(17,2.5,'euler','normal',1234))
        self.assertIn('walk',result[5]); self.assertTrue(result[5].endswith('cinematic'))
        self.assertEqual(joins.call_args.kwargs['seam_fade_ms'],27)
        self.assertFalse(joins.call_args.kwargs['enable_gain_match'])
        self.assertEqual(joins.call_args.kwargs['crossfade_ms'],0)

    def test_invalid_audio_policy_fails_before_sampling(self):
        for mode in ('source','invalid'):
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                self.execute([{'id':'one','type':'T2V','duration':1,'audio_mode':mode}])
        self.assertEqual(self.sampling_calls,[])

    def test_master_mixed_resolution_output_uses_enclosing_canvas(self):
        manager=ProjectCacheManager('regression',self.temp.name)
        for cid,shape in [('one',(5,32,64,3)),('two',(5,96,32,3))]:
            manager.store_clip_results(cid,cid,None,{'waveform':torch.ones((1,2,10000)),'sample_rate':48000},torch.ones(shape))
        result=self.execute([{'id':cid,'type':'T2V','duration':1,'validated':True} for cid in ('one','two')],model=None)
        self.assertEqual(result[0].shape,(10,96,64,3))
        self.assertEqual((result[2]['loaded_width'],result[2]['loaded_height']),(64,96))

    def test_sigma_shifts_and_external_schedule_reach_sampler(self):
        import comfy_extras.nodes_minimax_h3 as native
        sigmas=torch.linspace(1,0,8)
        with patch.object(native.MiniMaxH3SigmaShift,'execute',return_value=(self.model,)) as shifts:
            self.execute(shift_video=8.5,shift_audio=2.25,sigmas=sigmas)
        shifts.assert_called_once_with(self.model,8.5,2.25)
        self.assertIs(self.sampling_calls[0]['sigmas'],sigmas)

    def test_optional_passes_receive_current_controls(self):
        lift={'enabled':True,'test_setting':123}
        refinement={'enabled':True,'steps':4,'cfg':1.75,'denoise':.3,'target_width':64,'target_height':32,
                    'enable_tiling':True,'tile_count':3,'tile_overlap':16,'passes':2,'enable_latent_chunking':True,
                    'backend':'global','memory_budget_mb':256}
        face={'enabled':True,'strength':.25}
        bridge={'adapter':'controlled-fixture','alpha':.2}
        with patch('core.provenance.algorithm_provenance',return_value=[]), \
             patch('nodes.node_semantic_bridge.apply_semantic_bridge',side_effect=lambda cond,*a,**kw:cond) as semantic, \
             patch('nodes.node_director.sample_selflift',side_effect=lambda **kw:(kw['latent'],None)) as selflift, \
             patch('nodes.node_director.apply_refine_pass',side_effect=lambda **kw:kw['latent_dict']) as refine, \
             patch('core.tracked_face.refine_tracked_faces',side_effect=lambda frames,*a,**kw:(frames,{})) as faces:
            self.execute(selflift=lift,refine=refinement,face_refine=face,semantic_bridge=bridge)
        self.assertIs(selflift.call_args.kwargs['settings'],lift)
        self.assertIsNone(selflift.call_args.kwargs['carry'])
        for key in ('steps','cfg','denoise','target_width','target_height','enable_tiling','tile_count','tile_overlap','passes'):
            self.assertEqual(refine.call_args.kwargs[key],refinement[key])
        self.assertTrue(refine.call_args.kwargs['enable_chunking'])
        self.assertEqual(refine.call_args.kwargs['memory_budget_mb'],256)
        self.assertEqual(semantic.call_args.kwargs['task_key'],'T2VA')
        self.assertIs(faces.call_args.args[6],face)

    def test_missing_semantic_adapter_is_not_a_silent_noop(self):
        with patch('nodes.node_semantic_bridge.resolve_semantic_bridge_path',return_value=None):
            with self.assertRaisesRegex(RuntimeError,'adapter weights are missing'):
                self.execute(semantic_bridge={'adapter':'missing'})
        self.assertEqual(self.sampling_calls,[])

    def test_progress_identifies_only_the_clip_being_processed(self):
        clips=[{'id':'one','type':'T2V','duration':1},{'id':'two','type':'T2V','duration':1}]
        self.execute(clips,generation_mode='Next clip')
        clips[0]['validated']=True
        with patch('core.progress.shot_event') as events:
            self.execute(clips,generation_mode='Next clip',unique_id='42')
        stages=[call.args[2:4] for call in events.call_args_list]
        self.assertEqual(stages,[('two','preparing'),('two','sampling'),('two','completed')])
        self.assertTrue(all(call.args[:2]==('42','regression') for call in events.call_args_list))

    def test_first_pass_review_reuses_initial_sampling(self):
        refinement={'enabled':True,'mode':'refine','confirm_first_pass':True,'skip_fl2v':False}
        clips=[{'id':'one','type':'T2V','duration':1,'seed':'123'}]
        first=self.execute(clips,refine=refinement)
        pending=json.loads(first[9])['clips']
        self.assertTrue(pending[0]['refine_pending'])
        self.assertEqual(len(self.sampling_calls),1)
        self.assertFalse(ProjectCacheManager('regression',self.temp.name).result_availability()['one']['can_approve'])
        pending[0]['refine_approved']=True
        with patch('nodes.node_director.apply_refine_pass',side_effect=lambda **kw:kw['latent_dict']) as refine:
            final=self.execute(pending,refine=refinement)
        self.assertEqual(len(self.sampling_calls),1,'Initial sampling must not repeat when approving its matching first pass')
        refine.assert_called_once()
        self.assertFalse(json.loads(final[9])['clips'][0]['refine_pending'])
        self.assertTrue(ProjectCacheManager('regression',self.temp.name).result_availability()['one']['can_approve'])

    def test_changed_first_pass_requires_new_review(self):
        refinement={'enabled':True,'mode':'refine','confirm_first_pass':True}
        result=self.execute(refine=refinement)
        clips=json.loads(result[9])['clips'];clips[0]['refine_approved']=True;clips[0]['prompt']='different action'
        with patch('nodes.node_director.apply_refine_pass') as refine:
            result=self.execute(clips,refine=refinement)
        self.assertEqual(len(self.sampling_calls),2)
        refine.assert_not_called()
        self.assertTrue(json.loads(result[9])['clips'][0]['refine_pending'])

    def test_changed_continuity_settings_require_fresh_first_pass_review(self):
        refinement={'enabled':True,'mode':'refine','confirm_first_pass':True}
        clips=[{'id':'one','type':'T2V','duration':1},
               {'id':'two','type':'T2V','duration':1,'continuity':True,
                'continuity_mode':'Motion Context (Chained)','context_length':5,'audio_context_length':5}]
        self.execute([clips[0]]);clips[0]['validated']=True
        result=self.execute(clips,refine=refinement)
        clips=json.loads(result[9])['clips'];clips[1]['refine_approved']=True
        clips[1]['audio_context_length']=0
        with patch('nodes.node_director.apply_refine_pass') as refine:
            result=self.execute(clips,refine=refinement)
        self.assertEqual(len(self.sampling_calls),3,'Changed continuity settings cannot reuse an approved stale stage')
        refine.assert_not_called()
        self.assertFalse(json.loads(result[9])['clips'][1]['refine_approved'])

    def test_intermediate_refine_passes_are_cached_and_previewable(self):
        from core.preview import create_preview_plan
        result=self.execute(refine={'enabled':True,'mode':'refine','backend':'sampler','passes':2,'skip_fl2v':False})
        manager=ProjectCacheManager('regression',self.temp.name)
        self.assertEqual([row['pass'] for row in manager._manifest['clips']['one']['refine_passes']],[1,2])
        plan=create_preview_plan(json.loads(result[9]),'latest',self.temp.name,stream='pass:1')
        self.assertTrue(plan['found']);self.assertEqual(plan['clip_ids'],['one'])

    def test_typed_timeline_groups_route_and_preserve_local_approval(self):
        from nodes.node_timeline import MiniMaxH3TimelineBuilder
        group,=MiniMaxH3DirectorGroupImageToVideo().pack(prompt='external prompt',duration_sec=1,unique_id='group_node')
        external,_=MiniMaxH3TimelineBuilder().build(group)
        result=self.execute(timeline=external)
        clips=json.loads(result[9])['clips'];self.assertEqual(clips[0]['prompt'],'external prompt')
        clips[0]['validated']=True;self.sampling_calls.clear()
        self.execute(clips,timeline=external,model=None)
        self.assertEqual(self.sampling_calls,[])
        self.assertIn('timeline',self.node.INPUT_TYPES()['optional'])

    def test_hidden_execution_graph_is_not_used_as_prompt(self):
        result = self.execute(
            [{"id": "one", "type": "T2VA", "duration": 1., "prompt": ""}],
            config={"project_id": "regression", "run_mode": "full_batch", "prompt": "walk"},
            prompt={"private_graph_marker": {"class_type": "MiniMaxH3MasterNode"}},
        )
        self.assertEqual(result[5], "walk")

    def test_sampler_tensor_contract_and_metadata(self):
        tensor = torch.zeros((1, 24, 2, 2, 2))
        mask = torch.ones((1, 1, 2, 2, 2))
        sigmas = torch.linspace(1, 0, 4)
        output = sample_latent(self.model, {"samples": tensor, "noise_mask": mask, "batch_index": [0]},
            3, 1, "euler", "simple", [], [], 42, sigmas=sigmas)
        self.assertIs(output["samples"], tensor)
        self.assertIs(output["noise_mask"], mask)
        self.assertIs(self.sampling_calls[0]["sigmas"], sigmas)
        self.assertEqual(self.sampling_calls[0]["seed"], 42)

    def test_native_node_output_unwrapping(self):
        self.assertEqual(native_outputs(NativeOutput(1, 2)), (1, 2))
        self.assertEqual(native_outputs((1, 2)), (1, 2))

    def test_all_canonical_modes_route_to_correct_native_family(self):
        for mode in ("T2VA", "I2VA", "FL2VA", "L2VA", "REF2VA", "V2V", "RV2V", "Image Inpaint"):
            self.native_calls.clear()
            refs=[{"id":"first","type":"image","data":torch.zeros((1,32,32,3))},
                  {"id":"last","type":"image","data":torch.ones((1,32,32,3))},
                  {"id":"video","type":"video","data":torch.zeros((22,32,32,3))}]
            ids=({"I2VA":["first"],"FL2VA":["first","last"],"L2VA":["last"],
                  "V2V":["video"],"RV2V":["video","first"],"Image Inpaint":["first"]}).get(mode,[])
            self.execute([{ "id": "one", "type": mode, "duration": 1,"ref_ids":ids}], ref_pack={"refs":refs}, execution_mode="Conditioning Guide Output")
            expected = "MiniMaxH3ImageToVideo" if mode in ("T2VA", "I2VA", "FL2VA", "L2VA", "Image Inpaint") else "MiniMaxH3ReferenceToVideo"
            self.assertEqual(self.native_calls[0][0], expected)
            args=self.native_calls[0][1]
            if mode in ("I2VA","FL2VA","Image Inpaint"): self.assertIs(args["first_frame"],refs[0]["data"])
            if mode in ("L2VA","FL2VA"): self.assertIs(args["last_frame"],refs[1]["data"])
            if mode=="Image Inpaint": self.assertEqual(args["length"],5)
            if mode in ("V2V","RV2V"): self.assertEqual(len(args["ref_videos"]),1,"Source is never inserted twice")

    def test_generic_model_never_uses_wrong_family_socket(self):
        wrong_model = SimpleNamespace(model_name="wrong-family")
        self.execute(ref2va_model=wrong_model)
        self.assertIs(self.sampling_calls[0]["model"], self.model)

    def test_every_clip_type_runs_its_output_contract(self):
        refs=[{"id":"first","type":"image","data":torch.zeros((1,32,32,3))},
              {"id":"last","type":"image","data":torch.ones((1,32,32,3))},
              {"id":"source","type":"video","data":torch.ones((22,32,32,3))}]
        cases={"T2V":[],"I2V":["first"],"FL2V":["first","last"],"L2VA":["last"],
               "REF2VA":["first","source"],"V2V":["source"],"RV2V":["source","first"],"Image Inpaint":["first"]}
        for mode,ids in cases.items():
            with self.subTest(mode=mode):
                self.sampling_calls.clear();self.native_calls.clear()
                result=self.execute([{"id":mode.replace(' ','_'),"type":mode,"duration":1,"ref_ids":ids}],ref_pack={"refs":refs})
                self.assertEqual(len(self.sampling_calls),1)
                self.assertEqual(result[0].shape[0],1 if mode=='Image Inpaint' else 22 if mode in ('V2V','RV2V') else align_frame_count(24))
                self.assertIsNotNone(result[4].get('samples'))
        self.sampling_calls.clear();self.native_calls.clear()
        result=self.execute([{"id":"existing","type":"V2V","locked":True,"duration":1,"ref_ids":["source"]}],ref_pack={"refs":refs})
        self.assertEqual(self.sampling_calls,[]);self.assertEqual(self.native_calls,[])
        self.assertEqual(result[0].shape[0],22)
        from core.preview import create_preview_plan
        plan=create_preview_plan(json.loads(result[9]),scope='full',base_dir=self.temp.name)
        self.assertTrue(plan['found']);self.assertEqual(plan['clip_ids'],['existing'])

    def test_invalid_clip_assignments_fail_before_sampling(self):
        refs=[{"id":f"image{i}","type":"image","data":torch.zeros((1,32,32,3))} for i in range(10)]
        refs += [{"id":f"video{i}","type":"video","data":torch.zeros((22,32,32,3))} for i in range(4)]
        refs += [{"id":"long_video","type":"video","data":torch.zeros((384,32,32,3))},
                 {"id":"ten_video_a","type":"video","data":torch.zeros((240,32,32,3))},
                 {"id":"ten_video_b","type":"video","data":torch.zeros((240,32,32,3))},
                 {"id":"long_audio","type":"audio","data":{"waveform":torch.zeros((1,2,768000)),"sample_rate":48000}}]
        invalid=[('T2V',['image0']),('I2V',['image0','image1']),('FL2V',['image0','image1','image2']),
                 ('L2VA',['video0']),('Image Inpaint',['video0']),('V2V',['video0','video1']),
                 ('RV2V',[f'video{i}' for i in range(4)]),('REF2VA',[f'image{i}' for i in range(10)]),
                 ('I2V',[]),('FL2V',['image0']),('L2VA',[]),('V2V',[]),('RV2V',[]),
                 ('REF2VA',['long_video']),('RV2V',['ten_video_a','ten_video_b']),
                 ('REF2VA',['image0','long_audio']),('REF2VA',['long_audio'])]
        for mode,ids in invalid:
            with self.subTest(mode=mode,ids=ids),self.assertRaises(ValueError):
                self.execute([{"id":"invalid","type":mode,"duration":1,"ref_ids":ids}],ref_pack={"refs":refs})
        self.assertEqual(self.sampling_calls,[])

    def test_lazy_guide_mode_needs_no_model(self):
        self.assertEqual(self.node.check_lazy_status(config={"execution_mode": "Conditioning Guide Output"}), [])
        self.assertEqual(self.node.check_lazy_status(timeline_data=json.dumps({"clips": [{"type": "RV2V"}]})), ["ref2va_model"])

    def test_returned_latent_is_sampled_and_audio_matches_video(self):
        result = self.execute()
        self.assertIs(result[4]["samples"], self.sampling_calls[0]["samples"])
        self.assertEqual(result[1]["waveform"].shape[-1], round(result[7] / result[6] * 48000))
        self.assertEqual(result[2]["loaded_frame_count"], result[7])

    def test_approval_preserves_take_after_settings_change(self):
        clips = [{"id": "one", "type": "T2VA", "duration": 1, "prompt": "walk"}]
        self.execute(clips)
        clips[0]["validated"] = True
        self.sampling_calls.clear()
        self.execute(clips)
        self.assertEqual(self.sampling_calls, [])
        self.execute(clips, steps=26)
        self.assertEqual(self.sampling_calls, [])
        clips[0]["validated"] = False
        self.execute(clips, steps=26)
        self.assertEqual(len(self.sampling_calls), 1)

    def test_old_green_checkbox_skips_first_clip_and_completes_full_preview(self):
        from core.preview import create_preview_plan
        for generation in ('Next clip','All clips'):
            with self.subTest(generation=generation):
                pid='green_'+generation.split()[0].lower()
                clips=[{'id':'one','type':'T2V','duration':1,'seed':10},
                       {'id':'two','type':'T2V','duration':1,'seed':20}]
                config={'project_id':pid}
                self.execute(clips,config=config,generation_mode='Next clip')
                manager=ProjectCacheManager(pid,self.temp.name)
                original=manager._manifest['clips']['one']['generation']
                clips[0]['selected']=True  # The old checkbox shown in the user's screenshot.
                self.sampling_calls.clear()
                result=self.execute(clips,config=config,generation_mode=generation)
                self.assertEqual([call['seed'] for call in self.sampling_calls],[20])
                manager=ProjectCacheManager(pid,self.temp.name)
                self.assertEqual(manager._manifest['clips']['one']['generation'],original)
                state=json.loads(result[9]);self.assertTrue(state['clips'][0]['validated'])
                plan=create_preview_plan(state,'full',self.temp.name)
                self.assertEqual(plan['clip_ids'],['one','two']);self.assertEqual(plan['clip_count'],2)

    def test_approved_latent_only_take_restores_preview_without_sampling(self):
        result=self.execute()
        manager=ProjectCacheManager('regression',self.temp.name)
        original=manager._manifest['clips']['one']['generation']
        os.unlink(manager.get_clip_frames_path('one'));os.unlink(manager.get_clip_audio_path('one'))
        self.assertTrue(manager.result_availability()['one']['can_approve'])
        self.sampling_calls.clear()
        self.execute([{'id':'one','type':'T2VA','duration':1,'validated':True}])
        self.assertEqual(self.sampling_calls,[])
        manager=ProjectCacheManager('regression',self.temp.name)
        self.assertEqual(manager._manifest['clips']['one']['generation'],original)
        self.assertTrue(manager.result_availability()['one']['has_frames'])

    def test_empty_clip_cannot_reuse_or_silently_generate_an_approved_take(self):
        self.assertEqual(ProjectCacheManager('regression',self.temp.name).result_availability(),{})
        with self.assertRaisesRegex(ValueError,'no complete saved take'):
            self.execute([{'id':'empty','type':'T2V','duration':1,'validated':True}])
        self.assertEqual(self.sampling_calls,[])

    def test_reference_changes_preserve_approval_until_unapproved(self):
        clips = [{"id": "one", "type": "REF2VA", "duration": 1, "ref_ids": ["image_1"]}]
        self.execute(clips, ref_pack=MiniMaxH3RefPack().pack(image_1=torch.zeros((1, 32, 32, 3)))[0])
        clips[0]["validated"] = True
        self.sampling_calls.clear()
        self.execute(clips, ref_pack=MiniMaxH3RefPack().pack(image_1=torch.ones((1, 32, 32, 3)))[0])
        self.assertEqual(self.sampling_calls, [])
        clips[0]["validated"] = False
        self.execute(clips, ref_pack=MiniMaxH3RefPack().pack(image_1=torch.ones((1, 32, 32, 3)))[0])
        self.assertEqual(len(self.sampling_calls), 1)

    def test_upstream_changes_preserve_approved_successors(self):
        clips = [{"id": "one", "type": "T2VA", "duration": 1, "seed": 1},
                 {"id": "two", "type": "T2VA", "duration": 1, "seed": 2}]
        self.execute(clips)
        for clip in clips:
            clip["validated"] = True
        self.sampling_calls.clear()
        self.execute(clips)
        self.assertEqual(len(self.sampling_calls), 0)
        clips[0]["seed"] = 3
        self.execute(clips)
        self.assertEqual(self.sampling_calls, [])
        for clip in clips:
            clip["validated"] = False
        self.execute(clips)
        self.assertEqual([x["seed"] for x in self.sampling_calls], [3, 2])

    def test_independent_mode_does_not_invalidate_later_clip(self):
        clips = [{"id": "one", "type": "T2VA", "duration": 1, "seed": 1},
                 {"id": "two", "type": "T2VA", "duration": 1, "seed": 2}]
        self.execute(clips, continuity_mode="Independent (No Continuity)")
        clips[1]["validated"] = True
        self.sampling_calls.clear()
        clips[0]["seed"] = 3
        self.execute(clips, continuity_mode="Independent (No Continuity)")
        self.assertEqual([x["seed"] for x in self.sampling_calls], [3])

    def test_clip_by_clip_stops_after_one_new_shot(self):
        clips = [{"id": str(i), "type": "T2VA", "duration": 1} for i in range(3)]
        result = self.execute(clips, run_mode="clip_by_clip")
        self.assertEqual(len(self.sampling_calls), 1)
        self.assertEqual(result[7], 39)

    def test_native_text_and_groups_are_consumed(self):
        group, = MiniMaxH3DirectorGroupImageToVideo().pack(prompt="group prompt", duration_sec=1.)
        result = self.execute(i2v_groups=group, prompt_text="\nbridge prompt\n\n")
        self.assertEqual(result[5], "bridge prompt")

    def test_reference_group_size_reaches_native_conditioning(self):
        from nodes.node_groups import MiniMaxH3DirectorGroupReferenceToVideo
        group, = MiniMaxH3DirectorGroupReferenceToVideo().pack(
            prompt="A person turns", duration_sec=1., ref_image_size="1536",
            ref_image_1=torch.zeros((1, 32, 32, 3)))
        result = self.execute(r2v_groups=group, timeline_data="{}", continuity_mode="Independent (No Continuity)")
        native = next(kw for name, kw in self.native_calls if name == "MiniMaxH3ReferenceToVideo")
        self.assertEqual(native["ref_image_size"], "1536")
        self.assertNotIn("group", json.loads(result[9])["clips"][0])
        saved = json.loads((__import__("pathlib").Path(self.temp.name)/"regression"/"autosave.json").read_text())
        self.assertNotIn("group", saved["clips"][0])
        self.assertIsNotNone(group["ref_images"]["ref_image_1"])

    def test_original_canvas_uses_real_reference_pool_tensor_size(self):
        from core.resolution import timeline_media_size
        pack, = MiniMaxH3RefPack().pack(image_1=torch.zeros((1, 128, 256, 3)))
        with patch.dict(__import__("sys").modules, {"folder_paths": SimpleNamespace(get_input_directory=lambda: self.temp.name)}):
            self.assertEqual(timeline_media_size({}, pack), (256, 128))

    def test_fallback_reference_aliases_are_deduplicated(self):
        pack, = MiniMaxH3RefPack().pack(image_1=torch.zeros((1, 32, 32, 3)))
        self.execute(ref_pack=pack, timeline_data="{}", execution_mode="Conditioning Guide Output")
        self.assertEqual(len(self.native_calls[0][1]["ref_images"]), 1)

    def test_reference_motion_context_uses_native_guide(self):
        clips = [{"id": "one", "type": "T2VA", "duration": 1},
                 {"id": "two", "type": "REF2VA", "duration": 1}]
        result = self.execute(clips)
        guides = [kw for name, kw in self.native_calls if name == "MiniMaxH3AddGuide"]
        self.assertEqual(len(guides), 1)
        self.assertEqual(guides[0]["frame_idx"], 0)
        self.assertEqual(guides[0]["image"].shape[0], 22)
        self.assertEqual(result[7], 39 + 39)

    def test_per_shot_context_overrides_global_and_can_disable_audio(self):
        clips = [{"id":"one","type":"T2VA","duration":2,"continuity_mode":"Independent (No Continuity)"},
                 {"id":"two","type":"T2VA","duration":2,"continuity_mode":"Motion Context (Chained)","context_length":39,"audio_context_length":0}]
        self.execute(clips, continuity_mode="Independent (No Continuity)")
        guides = [kw for name,kw in self.native_calls if name=="MiniMaxH3AddGuide"]
        self.assertEqual(guides[0]["image"].shape[0],39)
        self.assertIsNone(guides[0].get("audio"))

    def test_independent_bypasses_tail_guides_and_carry(self):
        clips=[{"id":"one","type":"T2V","duration":2,"continuity_mode":"Independent (No Continuity)"},
               {"id":"two","type":"T2V","duration":2,"continuity_mode":"Independent (No Continuity)"}]
        self.execute(clips)
        builders=[kw for name,kw in self.native_calls if name=='MiniMaxH3ImageToVideo']
        self.assertEqual(len(builders),2)
        self.assertTrue(all(kw['first_frame'] is None for kw in builders))
        self.assertFalse(any(name=='MiniMaxH3AddGuide' for name,_ in self.native_calls))
        self.assertTrue(all(call['noise_mask'] is None for call in self.sampling_calls))

    def test_imported_footage_uses_budgeted_model_frames_for_next_clip_context(self):
        frames=torch.zeros((56,32,32,3))
        model_frames=torch.zeros((56,32,64,3))
        source={"frames":frames,"model_frames":model_frames,
                "audio":{"waveform":torch.zeros((1,2,112000)),"sample_rate":48000}}
        clips=[{"id":"footage","type":"V2V","duration":56/24,"source":{"filename":"source.mp4"},"locked":True},
               {"id":"next","type":"T2V","duration":2,"continuity_mode":"Motion Context (Chained)","context_length":22}]
        with patch('nodes.node_director.source_range',return_value=source):self.execute(clips)
        guide=next(kw for name,kw in self.native_calls if name=='MiniMaxH3AddGuide')
        self.assertEqual(guide['image'].shape,(22,32,64,3))
        self.assertEqual(len(self.sampling_calls),1,'Existing footage is not sampled')

    def test_video_edit_reference_uses_input_budget_not_output_canvas(self):
        source={"frames":torch.zeros((56,32,32,3)),"model_frames":torch.zeros((56,32,64,3)),
                "audio":{"waveform":torch.zeros((1,2,112000)),"sample_rate":48000}}
        with patch('nodes.node_director.source_range',return_value=source):
            self.execute([{"id":"edit","type":"V2V","duration":56/24,"source":{"filename":"source.mp4"}}])
        reference=next(kw for name,kw in self.native_calls if name=='MiniMaxH3ReferenceToVideo')
        self.assertEqual(reference['ref_videos']['ref_video_1'].shape,(56,32,64,3))

    def test_tail_handoff_uses_one_image_without_motion_or_audio_guides(self):
        clips=[{"id":"one","type":"T2V","duration":2,"continuity_mode":"Independent (No Continuity)"},
               {"id":"two","type":"T2V","duration":2,"continuity_mode":"FL2VA Tail Handoff","context_length":56,"audio_context_length":56}]
        self.execute(clips)
        builders=[kw for name,kw in self.native_calls if name=='MiniMaxH3ImageToVideo']
        self.assertEqual(builders[1]['first_frame'].shape[0],1)
        self.assertFalse(any(name=='MiniMaxH3AddGuide' for name,_ in self.native_calls))
        self.assertTrue(all(call['noise_mask'] is None for call in self.sampling_calls))
        self.assertEqual(ProjectCacheManager('regression',self.temp.name)._manifest['clips']['two']['trim_prefix'],1)

    def test_motion_context_slices_audio_independently_and_trims_borrowed_prefix(self):
        clips=[{"id":"one","type":"T2V","duration":2,"continuity_mode":"Independent (No Continuity)"},
               {"id":"two","type":"T2V","duration":2,"continuity_mode":"Motion Context (Chained)","context_length":39,"audio_context_length":5}]
        self.execute(clips)
        guide=next(kw for name,kw in self.native_calls if name=='MiniMaxH3AddGuide')
        self.assertEqual(guide['image'].shape[0],39)
        self.assertEqual(guide['audio']['waveform'].shape[-1],round(5/24*guide['audio']['sample_rate']))
        self.assertEqual(ProjectCacheManager('regression',self.temp.name)._manifest['clips']['two']['trim_prefix'],39)

    def test_master_timeline_generation_mode_overrides_config(self):
        clips=[{"id":"one","type":"T2VA","duration":1},{"id":"two","type":"T2VA","duration":1}]
        self.execute(timeline_data=json.dumps({"version":2,"project_id":"regression","generation_mode":"Next shot","clips":clips}),run_mode="full_batch")
        self.assertEqual(len(self.sampling_calls),1)

    def test_continuity_modes_validate_and_clamp_audio(self):
        from core.continuity import resolve_continuity
        result=resolve_continuity({"continuity_mode":"Latent Carry (Pinned)","context_length":5,"audio_context_length":56})
        self.assertEqual(result["audio_frames"],5)
        self.assertEqual(resolve_continuity({"continuity_mode":"FL2VA Tail Handoff"})["video_frames"],1)
        self.assertEqual(resolve_continuity({"continuity":False})["video_frames"],0)
        with self.assertRaises(ValueError):resolve_continuity({"context_length":12})

    def test_latent_carry_receives_per_shot_audio_policy(self):
        clips=[{"id":"one","type":"T2VA","duration":2,"continuity_mode":"Independent (No Continuity)"},
               {"id":"two","type":"T2VA","duration":2,"continuity_mode":"Latent Carry (Pinned)","context_length":39,"audio_context_length":5,"continuity_redraw":.3}]
        with patch('core.vendor.aimixer.director.h3_latent_continue.apply_latent_continue',side_effect=lambda latent,**kw:(latent,39,0)) as carry, patch('core.advanced_sampling.sample_stage',side_effect=lambda model,latent,*args,**kw:latent):
            self.execute(clips)
        self.assertEqual(carry.call_args.kwargs['context_length'],39)
        self.assertEqual(carry.call_args.kwargs['audio_context_length'],5)
        self.assertTrue(carry.call_args.kwargs['pin_audio'])
        self.assertEqual(carry.call_args.kwargs['seam_min_mask'],.3)

    def test_clip_by_clip_advances_only_the_completed_seed(self):
        clips = [{"id":"one","type":"T2V","duration":1,"seed":"18446744073709551615","seed_mode":"increment"},
                 {"id":"two","type":"T2V","duration":1,"seed":"42","seed_mode":"increment"}]
        result = self.execute(clips,run_mode="clip_by_clip")
        with open(os.path.join(self.temp.name,"regression","autosave.json"),encoding="utf-8") as stream:
            state = json.load(stream)
        self.assertEqual(state["clips"][0]["seed"],"0")
        self.assertEqual(state["clips"][0]["last_seed"],"18446744073709551615")
        self.assertEqual(state["clips"][1]["seed"],"42")
        self.assertNotIn("last_seed",state["clips"][1])
        self.assertEqual(result[1]["waveform"].shape[-1], round(result[7] / 24 * 48000))
        project = json.loads(result[9])
        self.assertEqual(project["project_id"],"regression")
        self.assertEqual(project["clips"][0]["last_seed"],"18446744073709551615")


    def test_tiles_cover_small_canvas_with_excessive_tile_count(self):
        from core.vendor.aimixer.director.spatial_tiled_sampling import compute_tile_starts
        starts, width = compute_tile_starts(4, 8, 32)
        covered = set()
        for start in starts:
            covered.update(range(start, min(4, start + width)))
        self.assertEqual(covered, set(range(4)))

    def test_inpaint_requires_one_image_and_non_native_fps_fail_clearly(self):
        with self.assertRaisesRegex(ValueError, "24 fps"):
            self.execute(frame_rate=30)
        with self.assertRaisesRegex(ValueError, "exactly one image"):
            self.execute([{ "id": "one", "type": "Image Inpaint", "duration": 1}])

    def test_upstream_image_inpaint_workflow_returns_one_generated_still(self):
        pack, = MiniMaxH3RefPack().pack(image_1=torch.zeros((1, 32, 32, 3)))
        result = self.execute([{ "id": "one", "type": "Image Inpaint", "duration": 8,
            "ref_ids": ["image_1"]}], ref_pack=pack)
        self.assertEqual(self.native_calls[0][1]["length"], 5)
        self.assertIsNotNone(self.native_calls[0][1]["first_frame"])
        self.assertEqual(result[7], 1)

    def test_lora_rows_validate_strength_and_enabled_flags(self):
        from core.loras import normalize_loras, resolve_lora_files
        self.assertEqual(resolve_lora_files([{"name": "disabled", "enabled": False}]), [])
        self.assertEqual(normalize_loras([{"name": "a", "strength": .5}]), [{"name": "a", "strength": .5}])
        with self.assertRaises(ValueError):
            normalize_loras([{"name": "a", "strength": float("nan")}])

    def test_lora_file_changes_change_content_signature(self):
        import sys
        from core.loras import resolve_lora_files
        path = os.path.join(self.temp.name, "weights.safetensors")
        folder_paths = SimpleNamespace(get_full_path_or_raise=lambda category, name: path)
        with patch.dict(sys.modules, {"folder_paths": folder_paths}):
            with open(path, "wb") as f: f.write(b"first")
            first = resolve_lora_files([{"name": "test"}])
            with open(path, "wb") as f: f.write(b"second")
            second = resolve_lora_files([{"name": "test"}])
        self.assertNotEqual(first[0]["sha256"], second[0]["sha256"])

    def test_shot_lora_does_not_leak_into_the_next_shot(self):
        import sys, types, comfy
        class Model(SimpleNamespace):
            def clone(self):
                return Model(model_name=self.model_name, patches=list(self.patches))
        base = Model(model_name="test-h3", patches=[])
        weights_path = os.path.join(self.temp.name, "weights.safetensors")
        with open(weights_path, "wb") as stream:
            stream.write(b"test checkpoint")
        paths = SimpleNamespace(get_full_path_or_raise=lambda category, name: weights_path)
        sd, utils = types.ModuleType("comfy.sd"), types.ModuleType("comfy.utils")
        def load(model, clip, state, strength_model, strength_clip):
            model.patches.append(strength_model)
            return model, clip
        sd.load_lora_for_models = load
        utils.load_torch_file = lambda path, safe_load: {"weights": "fixture"}
        with patch.dict(sys.modules, {"folder_paths": paths, "comfy.sd": sd, "comfy.utils": utils}), \
             patch.object(comfy, "sd", sd), patch.object(comfy, "utils", utils):
            self.execute([{ "id": "one", "type": "T2VA", "duration": 1,
                "loras": [{"name": "test", "strength": .7}]},
                {"id": "two", "type": "T2VA", "duration": 1}], model=base)
        self.assertEqual(self.sampling_calls[0]["model"].patches, [.7])
        self.assertEqual(self.sampling_calls[1]["model"].patches, [])
        self.assertEqual(base.patches, [])

    def test_source_edit_binds_video_one_and_keeps_original_audio(self):
        source = {"frames": torch.ones((17, 32, 32, 3)),
            "audio": {"waveform": torch.ones((1, 2, 32000)), "sample_rate": 32000}}
        with patch("nodes.node_director.source_range", return_value=source):
            result = self.execute([{ "id": "edit", "type": "RV2V", "duration": 1,
                "audio_mode": "source"}])
        self.assertIs(self.native_calls[0][1]["ref_videos"]["ref_video_1"], source["frames"])
        self.assertEqual(result[7], 17)
        self.assertEqual(result[1]["waveform"].shape[-1], 34000)
        manager=ProjectCacheManager('regression',self.temp.name)
        generation=manager._manifest['clips']['edit']['generation']
        os.unlink(manager.get_clip_audio_path('edit'))
        self.sampling_calls.clear()
        with patch("nodes.node_director.source_range", return_value=source):
            self.execute([{'id':'edit','type':'RV2V','duration':1,'audio_mode':'source','validated':True}])
        self.assertEqual(self.sampling_calls,[])
        self.assertEqual(ProjectCacheManager('regression',self.temp.name)._manifest['clips']['edit']['generation'],generation)

    def test_unselected_source_shot_passes_through_without_sampling(self):
        source = {"frames": torch.ones((17, 32, 32, 3)),
            "audio": {"waveform": torch.ones((1, 2, 32000)), "sample_rate": 32000}}
        with patch("nodes.node_director.source_range", return_value=source):
            result = self.execute(timeline_data=json.dumps({"run_selection": True,
                "clips": [{"id": "skip", "type": "V2V", "duration": 1, "selected": False}]}))
        self.assertEqual(self.sampling_calls, [])
        self.assertEqual(result[7], 17)
        self.assertTrue(bool((result[0] == 1).all()))


    def test_source_mute_policy_has_exact_visible_duration(self):
        from core.source_media import choose_audio
        audio = choose_audio("mute", {}, None, 17)
        self.assertEqual(audio["waveform"].shape[-1], 34000)
        self.assertTrue(bool((audio["waveform"] == 0).all()))

    def test_cache_paths_cannot_escape_project(self):
        for name in ("..", "../escape", "C:\\escape", "CON", "name."):
            with self.assertRaises(ValueError):
                ProjectCacheManager(name, self.temp.name)
        manager = ProjectCacheManager("safe", self.temp.name)
        with self.assertRaises(ValueError):
            manager.get_clip_latent_path("../../escape")

    def test_absolute_input_path_must_obey_supplied_root(self):
        path = os.path.join(self.temp.name, "outside.txt")
        with open(path, "w") as f:
            f.write("x")
        root = os.path.join(self.temp.name, "input")
        os.mkdir(root)
        with self.assertRaises(ValueError):
            resolve_input_path(path, root)

    def test_import_cannot_assign_fingerprint_to_existing_cache(self):
        manager = ProjectCacheManager("safe", self.temp.name)
        from core.config import PROJECT_FORMAT, PROJECT_FORMAT_VERSION
        project = {"format": PROJECT_FORMAT, "version": PROJECT_FORMAT_VERSION, "timeline": {"clips": []},
            "server_cache_manifest": {"one": {"fingerprint": "forged", "validated": True}}}
        manager.import_lightweight_project_data(project)
        self.assertEqual(manager._manifest["clips"], {})

    def test_media_hash_depends_on_contents_and_order(self):
        zero, one = torch.zeros((1, 2)), torch.ones((1, 2))
        self.assertNotEqual(fingerprint_value([zero, one]), fingerprint_value([one, zero]))
        self.assertEqual(fingerprint_value(zero), fingerprint_value(zero.clone()))

    def test_audio_duration_padding_and_trimming(self):
        audio = {"waveform": torch.zeros((1, 2, 5)), "sample_rate": 48000}
        self.assertEqual(fit_audio_duration(audio, 24)["waveform"].shape[-1], 48000)

    def test_invalid_json_and_duplicate_ids_do_not_generate(self):
        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            self.execute(timeline_data="broken")
        with self.assertRaisesRegex(ValueError, "unique"):
            self.execute([{ "id": "same", "type": "T2VA"}, {"id": "same", "type": "T2VA"}])
        self.assertEqual(self.sampling_calls, [])

    def test_deleted_last_shot_does_not_generate_a_fallback(self):
        with self.assertRaisesRegex(ValueError, "no shots.*Add Shot"):
            self.execute(timeline_data=json.dumps({"clips": []}))
        self.assertEqual(self.sampling_calls, [])

    def test_invalid_sigmas_do_not_reach_sampler(self):
        with self.assertRaisesRegex(ValueError, "SIGMAS"):
            self.execute(sigmas=torch.tensor([0., 1., 0.]))
        self.assertEqual(self.sampling_calls, [])

    def test_refmod_audio_reports_actual_token_length(self):
        from core.executor import MasterDirectorExecutor
        class Clip:
            def tokenize(self, text, **kwargs): return kwargs
            def encode_from_tokens_scheduled(self, tokens): return [[torch.zeros((1, 2, 5120)), {}]]
        positive, _, _ = MasterDirectorExecutor().build_conditioning(
            mode="REF2VA", prompt="sound", width=32, height=32, duration=1,
            clip=Clip(), vae=self.vae, audio_vae=self.audio_vae,
            refmod_items=[{"kind": "audio", "latent": torch.zeros((1, 32, 2, 17))}])
        self.assertEqual(positive[0][1]["minimax_refs"][0]["ref_audio_t"], 17)

    def test_multiple_cache_managers_preserve_manifest_entries(self):
        a, b = ProjectCacheManager("shared", self.temp.name), ProjectCacheManager("shared", self.temp.name)
        latent = {"samples": (torch.zeros((1, 24, 2, 2, 2)), torch.zeros((1, 32, 2, 8)))}
        a.store_clip_results("one", "a", latent)
        b.store_clip_results("two", "b", latent)
        self.assertTrue(a.is_clip_cached_and_valid("one", "a"))
        self.assertTrue(a.is_clip_cached_and_valid("two", "b"))

    def test_ffmpeg_failure_is_not_reported_as_success(self):
        import io
        from nodes.node_video_combine import MiniMaxH3VideoCombine
        process = SimpleNamespace(stdin=io.BytesIO(), returncode=1, wait=lambda: 1)
        with patch("nodes.node_video_combine.FFMPEG_PATH", "ffmpeg"), \
             patch("nodes.node_video_combine.resolve_output_path", return_value=(os.path.join(self.temp.name, "bad.mp4"), "bad.mp4", "")), \
             patch("nodes.node_video_combine.subprocess.Popen", return_value=process):
            with self.assertRaisesRegex(RuntimeError, "ffmpeg failed"):
                MiniMaxH3VideoCombine().combine_video(torch.zeros((5, 32, 32, 3)), encoder_backend="ffmpeg")



if __name__ == "__main__":
    unittest.main()
