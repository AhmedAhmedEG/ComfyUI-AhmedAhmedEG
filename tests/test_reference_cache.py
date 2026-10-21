import json
from pathlib import Path
import tempfile
import unittest
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

if __name__=='__main__':unittest.main()
