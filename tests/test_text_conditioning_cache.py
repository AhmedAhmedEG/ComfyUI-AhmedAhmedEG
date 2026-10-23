import tempfile
import unittest
from types import SimpleNamespace

import torch

from core.text_conditioning_cache import TextConditioningCache
from core.stage_progress import StageProgress, ProgressEncoder, _current, cache_clip, cache_report
from core.run_resources import RunResources, _current as resource_context


class Encoder:
    def __init__(self):
        self._mmx_provenance={'checkpoint':'test-sha'}
        self.patcher=SimpleNamespace(forced_hooks=None,patches={},object_patches={},model_options={})
        self.calls=0

    def encode_from_tokens_scheduled(self,tokens,**kwargs):
        self.calls+=1
        return [[torch.tensor([float(self.calls)]),{'pooled_output':torch.ones(2),'tag':'image'}]]


class TextConditioningTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.cache=TextConditioningCache(self.temp.name)
        self.encoder=Encoder()
        self.reporter=StageProgress(lambda _:None)
        token=_current.set(self.reporter);self.addCleanup(_current.reset,token)
        cache_clip('one',1,2)

    def test_disk_reuse_restart_and_mutation_isolation(self):
        args=({'tokens':[1,2],'image':torch.ones(2)},)
        first=self.cache.encode(self.encoder,args,{})
        first[0][0].fill_(99)
        restarted=TextConditioningCache(self.temp.name)
        other_encoder=Encoder()
        second=restarted.encode(other_encoder,args,{})
        self.assertEqual(other_encoder.calls,0)
        self.assertEqual(second[0][0].item(),1)
        second[0][0].fill_(88)
        self.assertEqual(restarted.encode(other_encoder,args,{})[0][0].item(),1)
        self.assertEqual(cache_report()['stats']['Text conditioning'],{'hit':2,'miss':1,'bypass':0})

    def test_actual_tokens_references_encoder_and_options_invalidate(self):
        image=torch.ones(2)
        args=({'text':'walk','image':image},)
        self.cache.encode(self.encoder,args,{})
        self.cache.encode(self.encoder,args,{})
        self.assertEqual(self.encoder.calls,1)
        image.add_(1)
        self.cache.encode(self.encoder,args,{})
        self.cache.encode(self.encoder,({'text':'run','image':image},),{})
        self.encoder.layer_idx=2
        self.cache.encode(self.encoder,args,{})
        self.encoder._mmx_provenance={'checkpoint':'different'}
        self.cache.encode(self.encoder,args,{})
        self.encoder.patcher.patches={'weight':torch.ones(1)}
        self.cache.encode(self.encoder,args,{})
        self.cache.encode(self.encoder,args,{'unprojected':True})
        self.assertEqual(self.encoder.calls,7)

    def test_hooks_and_opaque_options_bypass(self):
        self.encoder.patcher.forced_hooks=object()
        for _ in range(2):self.cache.encode(self.encoder,({},),{})
        self.encoder.patcher.forced_hooks=None
        self.encoder.patcher.model_options={'callback':lambda:None}
        self.cache.encode(self.encoder,({},),{})
        self.assertEqual(self.encoder.calls,3)
        self.assertEqual(cache_report()['stats']['Text conditioning']['bypass'],3)
        self.assertFalse(self.cache.folder.exists())

    def test_nested_token_structure_cannot_alias(self):
        self.assertNotEqual(self.cache.key(self.encoder,([[],[1]],),{}),
                            self.cache.key(self.encoder,([[1],[]],),{}))
        self.assertNotEqual(self.cache.key(self.encoder,({'x':[]},),{}),
                            self.cache.key(self.encoder,(['x'],),{}))

    def test_corrupt_files_recompute_and_entry_limit(self):
        self.cache.limit_entries=2
        args=({'text':'a'},)
        self.cache.encode(self.encoder,args,{})
        path=self.cache.folder/(self.cache.key(self.encoder,args,{})+'.pt')
        path.write_bytes(b'bad cache')
        self.cache.encode(self.encoder,args,{})
        self.assertEqual(self.encoder.calls,2)
        for value in ['b','c']:self.cache.encode(self.encoder,({'text':value},),{})
        self.assertEqual(len(list(self.cache.folder.glob('*.pt'))),2)
        self.cache.limit_bytes=1
        self.cache.encode(self.encoder,({'text':'large'},),{})
        self.assertFalse((self.cache.folder/(self.cache.key(self.encoder,({'text':'large'},),{})+'.pt')).exists())

    def test_progress_encoder_uses_run_cache_and_reports_per_clip(self):
        owner=RunResources();owner.text_conditioning=self.cache
        token=resource_context.set(owner)
        try:
            wrapper=ProgressEncoder(self.encoder)
            wrapper.encode_from_tokens_scheduled({'text':'same'})
            cache_clip('two',2,2)
            wrapper.encode_from_tokens_scheduled({'text':'same'})
            self.assertEqual(self.encoder.calls,1)
            self.assertEqual(cache_report()['stats']['Text conditioning']['hit'],1)
            self.assertEqual(self.reporter.cache_stats['one']['Text conditioning']['miss'],1)
        finally:resource_context.reset(token)


if __name__=='__main__':unittest.main()
