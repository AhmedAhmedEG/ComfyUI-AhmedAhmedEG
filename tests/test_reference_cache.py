import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import torch
from safetensors import safe_open
from core.reference_cache import ReferenceEncodeCache
from core.refmod import load_refmods


class VAE:
    output_device = 'cpu'
    def __init__(self, identity='video', audio=False):
        self._mmx_provenance = {'checkpoint':identity}
        self.calls = 0
        self.audio = audio
    def encode(self, data):
        self.calls += 1
        shape = (1,64,4) if self.audio else (1,24,1,2,2)
        return torch.arange(torch.tensor(shape).prod()).reshape(shape).float() + data.sum()


class ReferenceCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.data=torch.arange(48).reshape(1,4,4,3).float()
        self.vae=VAE()
    def cache(self, data=None, vae=None, signature='native-v1', limit=128*1024**2):
        cache=ReferenceEncodeCache(limit)
        key=cache.source_key('image',self.data if data is None else data)
        cache.configure(self.root,[key],signature,[vae or self.vae])
        return cache,key
    def encode(self,cache,key,vae=None,data=None):
        with cache.asset(key):return cache.wrap(vae or self.vae).encode(self.data if data is None else data)
    def test_refmod_layout_and_exact_reuse_across_runs(self):
        cache,key=self.cache();first=self.encode(cache,key)
        first[0,0,0,0,0]=-999
        second=self.encode(cache,key)
        self.assertNotEqual(second.flatten()[0],-999)
        self.assertEqual(self.vae.calls,1)
        path=next((self.root/'reference_latents').glob('*.safetensors'))
        with safe_open(path,framework='pt') as handle:
            self.assertEqual(list(handle.keys()),['latent'])
            self.assertEqual(json.loads(handle.metadata()['refmod_meta'])['kind'],'image')
        with patch('core.refmod.find_refmod_path',return_value=str(path.with_suffix(''))):
            loaded,metadata=load_refmods('prepared')[0]
        self.assertTrue(torch.equal(loaded,second))
        replacement=VAE();cache,key=self.cache(vae=replacement)
        self.assertTrue(torch.equal(self.encode(cache,key,replacement),second))
        self.assertEqual(replacement.calls,0)
    def test_audio_uses_refmod_layout_and_restores_native_shape(self):
        vae=VAE('audio',True);cache,key=self.cache(vae=vae)
        expected=self.encode(cache,key,vae)
        path=next((self.root/'reference_latents').glob('*.safetensors'))
        with safe_open(path,framework='pt') as handle:self.assertEqual(tuple(handle.get_tensor('latent').shape),(1,32,2,4))
        fresh=VAE('audio',True);cache,key=self.cache(vae=fresh)
        self.assertTrue(torch.equal(self.encode(cache,key,fresh),expected))
        self.assertEqual(fresh.calls,0)
    def test_input_native_code_and_vae_changes_force_reencode(self):
        cache,key=self.cache();self.encode(cache,key)
        for data,vae,signature in [(self.data+1,self.vae,'native-v1'),(self.data,VAE('other'),'native-v1'),(self.data,self.vae,'native-v2')]:
            before=vae.calls;cache,key=self.cache(data,vae,signature)
            self.encode(cache,key,vae,data)
            self.assertEqual(vae.calls,before+1)
    def test_disconnect_prunes_only_derived_files_and_malformed_index_is_safe(self):
        cache,key=self.cache();self.encode(cache,key)
        folder=self.root/'reference_latents';unrelated=folder/'original.safetensors';unrelated.write_bytes(b'original')
        index=json.loads((folder/'index.json').read_text());index['bad']={'owners':[{}]}
        (folder/'index.json').write_text(json.dumps(index))
        cache.configure(self.root,[],vaes=[self.vae])
        self.assertEqual(list(folder.glob('*.safetensors')),[unrelated])
        self.assertEqual(cache.index,{})
    def test_corrupt_file_recovers_and_ram_is_bounded(self):
        cache,key=self.cache(limit=4);expected=self.encode(cache,key)
        self.assertEqual(cache.bytes,0)
        path=next((self.root/'reference_latents').glob('*.safetensors'));path.write_bytes(b'broken')
        cache,key=self.cache(limit=4)
        self.assertTrue(torch.equal(self.encode(cache,key),expected))
        self.assertEqual(self.vae.calls,2)

    def test_preparation_record_skips_native_prepass_after_restart(self):
        from core.executor import MasterDirectorExecutor
        from core.run_resources import _current
        cache=ReferenceEncodeCache();cache.register_source('asset:one','image',self.data)
        cache.configure(self.root,['asset:one'],'native-v1',[self.vae])
        calls=[]
        class Native:
            @staticmethod
            def execute(**options):
                calls.append(options)
                options['vae'].encode(options['ref_images']['ref_image_1']+1)
        executor=MasterDirectorExecutor.__new__(MasterDirectorExecutor)
        asset={'type':'image','data':self.data}
        def prepare(cache,duration=1,ref_size='match'):
            token=_current.set(SimpleNamespace(reference_encodes=cache))
            try:
                with patch('core.executor.get_native_h3_node',return_value=Native):
                    executor.prepare_reference_encodes([asset],32,32,duration,self.vae,None,ref_size)
            finally:_current.reset(token)
        prepare(cache);self.assertEqual(len(calls),1)
        cache=ReferenceEncodeCache();cache.register_source('asset:one','image',self.data)
        cache.configure(self.root,['asset:one'],'native-v1',[self.vae])
        prepare(cache);self.assertEqual(len(calls),1,'Warm run skips native prepass')
        prepare(cache,duration=2);self.assertEqual(len(calls),2,'Duration participates in native preparation')
        self.data.add_(1)
        prepare(cache);self.assertEqual(len(calls),3,'Changed input cannot reuse a preparation record')
        request=next(iter(cache.preparations))
        path=self.root/'reference_latents'/(cache.preparations[request][0]+'.safetensors');path.unlink()
        self.assertFalse(cache.preparation_ready(request))

    def test_unchanged_index_is_not_rewritten(self):
        cache,key=self.cache();self.encode(cache,key)
        path=self.root/'reference_latents'/'index.json';before=path.stat().st_mtime_ns
        cache.configure(self.root,[key],'native-v1',[self.vae])
        self.assertEqual(path.stat().st_mtime_ns,before)

    def test_stable_owner_prunes_disconnected_inputs_without_reading_tensors(self):
        cache=ReferenceEncodeCache();cache.configure(self.root,['asset:one'],'native-v1',[self.vae])
        with cache.asset('asset:one'):cache.wrap(self.vae).encode(self.data)
        with patch('core.reference_cache._input_key',side_effect=AssertionError('No media hashing during cleanup')):
            cache.configure(self.root,[],'native-v1',[self.vae])
        self.assertEqual(cache.index,{})
        self.assertFalse(list((self.root/'reference_latents').glob('*.safetensors')))

if __name__=='__main__':unittest.main()
