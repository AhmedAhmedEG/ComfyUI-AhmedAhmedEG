import unittest
from core.stage_progress import StageProgress, ProgressEncoder, _current, bind, clip_stage


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
