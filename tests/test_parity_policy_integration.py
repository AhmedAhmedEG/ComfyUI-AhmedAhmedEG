import json,tempfile,unittest,types
from unittest.mock import patch
from tests.mock_torch import setup_mock_torch_if_needed
torch=setup_mock_torch_if_needed()
from core.refine_controls import refine_seed,refine_canvas
from core.project_conversion import convert_project
from core.forge_cast import clip_bindings,compile_cast_prompt
from core.forge import draft_prompts,apply_draft
from core.local_llm import LocalProvider


class PolicyIntegration(unittest.TestCase):
    def test_refine_seed_contract_including_uint64_wrap(self):
        self.assertEqual([refine_seed(7,'inherit',pass_index=i) for i in range(3)],[7,7,7])
        self.assertEqual([refine_seed(7,'offset',pass_index=i) for i in range(3)],[8,9,10])
        self.assertEqual(refine_seed(7,'independent','18446744073709551615',1),0)
        with self.assertRaises(ValueError):refine_seed(7,'independent','18446744073709551616')

    def test_follow_canvas_uses_actual_latent_aspect(self):
        video=torch.zeros((1,24,2,30,54))
        w,h=refine_canvas(video,'follow',1.8,1280,1280)
        self.assertEqual((w%32,h%32),(0,0));self.assertAlmostEqual(w/h,54/30,delta=.05)
        self.assertAlmostEqual(w*h/1e6,1.8,delta=.1)

    def test_sampler_passes_receive_independent_policy_seed_and_callback(self):
        from core.refine import apply_refine_pass
        latent={'samples':(torch.zeros((1,24,2,2,2)),torch.zeros((1,32,2,8)))}
        seeds=[];rounds=[]
        def sample(*args,**kw):seeds.append(args[8]);return args[1]
        with patch('core.refine.sample_latent',side_effect=sample):
            apply_refine_pass(object(),latent,[],[],7,passes=3,seed_policy='independent',refine_seed_value='100',pass_callback=lambda n,l:rounds.append(n))
        self.assertEqual(seeds,[100,101,102]);self.assertEqual(rounds,[1,2,3])

    def test_tritant_context_zero_translates_follow_video_not_mute(self):
        state,_=convert_project({'extender':{'generation_mode':'ref2va','settings':{'motion_context':True,'context_length':'39','audio_context_length':0},'clips_json':{'clips':[{'prompt':'p','duration':2}]}}},'tritant')
        row=state['clips'][0];self.assertEqual(row['context_length'],39);self.assertEqual(row['audio_context_length'],39)

    def test_foreign_conversion_preserves_canonical_fields_and_remaps_guides(self):
        source={'global':{'taskType':'ref2v'},'segments':[{'duration':2,'prompt':'walk','continuity_mode':'Latent Carry','context_length':56,'audio_context_length':39,
            'images':[{'id':'hero','filename':'hero.png'}], 'guides':[{'ref_id':'hero','frame_idx':24}], 'loras':[{'lora_name':'hero.safetensors','strength_model':.7}]}]}
        state,report=convert_project(source,'aimixer');row=state['clips'][0]
        self.assertEqual(row['continuity_mode'],'Latent Carry (Pinned)');self.assertEqual(row['context_length'],56)
        self.assertEqual(row['guides'],[{'ref_id':state['references'][0]['id'],'time':1}])
        self.assertEqual(row['loras'],[{'name':'hero.safetensors','strength':.7}]);self.assertFalse(row['validated'])
        self.assertFalse(report['cache_imported'])

    def test_current_conversion_preserves_extra_authoring_controls(self):
        state,_=convert_project({'version':2,'clips':[{'id':'a','prompt':'p','duration':2,'ref_ids':['x'],'continuity_mode':'Motion Context (Chained)','context_length':39,'seed_mode':'increment','refmods':[{'slot':1}],'guides':[{'ref_id':'x','time':1}]}]},'current')
        row=state['clips'][0];self.assertEqual(row['context_length'],39);self.assertEqual(row['seed_mode'],'increment');self.assertEqual(row['refmods'],[{'slot':1}])

    def test_cast_ignore_does_not_renumber_native_picture_slots(self):
        state={'available_refs':[{'id':'ignored','type':'image','forge_include':False},{'id':'hero','type':'image','characters':[2],'position':'left','retention':'attribute_transfer','description':'raised arms'}]}
        rows=clip_bindings(state,{'ref_ids':['ignored','hero']})
        self.assertEqual(rows[0]['label'],'<Picture 2>')
        prompt=compile_cast_prompt('Character 2 walks',rows)
        self.assertIn('<Subject 2> walks',prompt);self.assertIn('attribute_transfer',prompt);self.assertIn('<Picture 2>',prompt)

    def test_local_handle_releases_on_provider_exception(self):
        calls=[]
        def fail(*args,**kw):raise RuntimeError('draft failed')
        fail.release=lambda:calls.append('release')
        provider=LocalProvider({},'unload_after_draft')
        with patch('core.local_llm._load_local_provider',return_value=fail):
            with self.assertRaises(RuntimeError):provider([])
        self.assertEqual(calls,['release'])

    def test_disabled_foreign_lora_stays_disabled_for_native_consumer(self):
        state,_=convert_project({'global':{'taskType':'t2v'},'segments':[{'prompt':'p','duration':2,'loras':[{'name':'x.safetensors','active':False,'strength':.5}]}]},'aimixer')
        from core.loras import normalize_loras
        self.assertFalse(state['clips'][0]['loras'][0]['enabled'])
        self.assertEqual(normalize_loras(state['clips'][0]['loras']),[])

    def test_append_prompt_retains_native_reference_binding_with_fresh_id(self):
        state={'clips':[{'id':'a','type':'REF2VA','duration':2,'prompt':'p','ref_ids':['hero']}]}
        draft=draft_prompts(state,'continue',backend='local',generator=lambda *a,**kw:'{"shots":[{"prompt":"walk","type":"REF2VA","duration":2}]}')
        appended=apply_draft(state,draft,'append')['clips'][-1]
        self.assertEqual(appended['ref_ids'],['hero']);self.assertNotEqual(appended['id'],'a');self.assertFalse(appended['validated'])

    def test_tail_draft_applies_to_target_and_rejects_changed_take(self):
        state={'project_id':'p','approval_control_version':1,'clips':[{'id':'one','type':'T2V','prompt':'keep','duration':2},{'id':'two','type':'T2V','prompt':'old','duration':2}]}
        frames=torch.zeros((3,32,32,3))
        generator=lambda *a,**kw:json.dumps({'shots':[{'prompt':'continue','duration':2,'type':'T2V'}]})
        with patch('core.forge_context.predecessor_context',return_value=(frames,'generation-one')):
            draft=draft_prompts(state,'continue',backend='local',generator=generator,continuation_clip_id='two')
            applied=apply_draft(state,draft);self.assertEqual(applied['clips'][0]['prompt'],'keep');self.assertEqual(applied['clips'][1]['prompt'],'continue')
        with patch('core.forge_context.predecessor_context',return_value=(None,'new-generation')):
            with self.assertRaisesRegex(ValueError,'predecessor take changed'):apply_draft(state,draft)

