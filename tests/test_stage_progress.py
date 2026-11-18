import unittest
from core.stage_progress import StageProgress, ProgressEncoder, _current, bind, clip_stage


class NativeProgressTests(unittest.TestCase):
    def test_counted_stages_drive_native_bar_but_sampling_does_not(self):
        from unittest.mock import patch
        import core.stage_progress as module
        calls=[];reporter=StageProgress(lambda data:None,lambda:0.0);reporter.node='1'
        with patch.object(module,'_native_progress',lambda step,steps:calls.append((step,steps))):
            reporter.report('Encoding reference 1/2',step=0,steps=2)
            reporter.report('Sampling H3',step=1,steps=8)
            reporter.report('Video VAE · loading as needed and decoding frames')
        self.assertEqual(calls,[(0,2)])

    def test_lora_stage_names_each_file(self):
        from unittest.mock import patch, MagicMock
        import sys, types
        from core import loras
        sent=[];reporter=StageProgress(sent.append,lambda:0.0);reporter.node='1';token=_current.set(reporter)
        model=MagicMock();patched=MagicMock();patched.patches={}
        model.clone.return_value=patched
        def load(model,clip,state,strength,clip_strength):
            result=MagicMock();result.patches={'w':[1]*(len(model.patches.get('w',[]))+1)};return result,None
        fake_sd=types.SimpleNamespace(load_lora_for_models=load)
        fake_utils=types.SimpleNamespace(load_torch_file=lambda path,safe_load=True:{'w':1})
        try:
            with patch.dict(sys.modules,{'comfy':types.SimpleNamespace(sd=fake_sd,utils=fake_utils),'comfy.sd':fake_sd,'comfy.utils':fake_utils}):
                loras.apply_loras(model,[{'path':'/x/turbo_8step.safetensors','sha256':'a','name':'turbo_8step.safetensors','strength':1.0}],{})
        finally:_current.reset(token)
        labels=[row['label'] for row in sent]
        self.assertIn('LoRA · reading turbo_8step.safetensors',labels)
        self.assertIn('LoRA · 1 ready',labels)


class AdvancedSamplingProgressTests(unittest.TestCase):
    def test_latent_carry_and_selflift_samplers_report_steps(self):
        # Continuity (latent carry) and SelfLift use their own samplers; the
        # top bar must still switch from "Loading" to "Sampling" with steps.
        from unittest.mock import patch
        from core import advanced_sampling
        for name, target, call in (
            ('carry', 'core.vendor.aimixer.director.core_sampling.sample_single_stage',
             lambda: advanced_sampling.sample_stage(object(), {}, 4, 1., 'euler', 'simple', [], [], 1)),
            ('selflift', 'core.vendor.aimixer.director.selflift.sample.sample_selflift_stage',
             lambda: advanced_sampling.sample_selflift(object(), [], [], {}, 1, 4, 1., 'euler', 'simple',
                                                       {'enabled': True}, None, 64, 64))):
            with self.subTest(name):
                sent=[];reporter=StageProgress(sent.append,lambda:0.0);reporter.node='1';token=_current.set(reporter)
                def fake(**kwargs):
                    for step in range(4): kwargs['on_step_preview'](step, 4, None)
                    return {}
                try:
                    with patch(target, side_effect=fake), \
                         patch('core.vendor.aimixer.director.selflift.pack.normalize_selflift_pack', return_value={}):
                        call()
                finally:_current.reset(token)
                labels=[row['label'] for row in sent]
                self.assertEqual(labels[0],'H3 model · loading as needed and initializing sampler')
                self.assertEqual([(r['step'],r['steps']) for r in sent if r['label']=='Sampling H3'][-1],(4,4))


class StageProgressTests(unittest.TestCase):
    def test_duplicates_throttle_and_final_update(self):
        sent, now = [], [0.]
        reporter=StageProgress(sent.append,lambda:now[0])
        reporter.report('Unbound')
        self.assertEqual(sent,[])
        reporter.node='12';reporter.project='test'
        reporter.report('Preparing');reporter.report('Preparing')
        self.assertEqual(len(sent),1)
        now[0]=1;reporter.report('Sampling',step=1,steps=4)
        reporter.report('Sampling',step=2,steps=4)
        self.assertEqual(len(sent),2)
        reporter.report('Sampling',step=4,steps=4)
        self.assertEqual(sent[-1]['step'],4)
        reporter.report('Finished',active=False)
        self.assertFalse(sent[-1]['active'])

    def test_encoder_delegates_tokens_options_and_result_without_copying(self):
        sent=[];reporter=StageProgress(sent.append);token=_current.set(reporter)
        class Encoder:
            other='unchanged'
            def tokenize(self,text,**kwargs):return (text,kwargs)
            def encode_from_tokens_scheduled(self,tokens):return tokens
        try:
            bind('12','project');clip_stage('12','project','one','preparing',index=1,total=4)
            encoder=ProgressEncoder(Encoder())
            tokens=encoder.tokenize('walk',refs=['one'])
            self.assertIs(encoder.encode_from_tokens_scheduled(tokens),tokens)
            self.assertEqual(tokens,('walk',{'refs':['one']}))
            self.assertEqual(encoder.other,'unchanged')
            self.assertEqual(sent[-1]['clip_id'],'one')
            self.assertEqual(sent[-1]['total'],4)
        finally:_current.reset(token)


if __name__=='__main__':unittest.main()
