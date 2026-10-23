import gc
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import weakref

import torch
from core.file_fingerprints import FileFingerprintCache
from core.tensor_fingerprints import TensorFingerprintCache
from core.cache_manager import fingerprint_value
from core.reference_cache import _input_key


class FileFingerprintTests(unittest.TestCase):
    def test_restart_reuses_digest_and_replacement_invalidates_even_with_same_mtime(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); model=root/'model'; index=root/'hashes.json'
            model.write_bytes(b'original'); before=model.stat()
            first=FileFingerprintCache(index).get(model)
            with patch('core.file_fingerprints.hashlib.file_digest',side_effect=AssertionError('Unexpected full read')):
                self.assertEqual(FileFingerprintCache(index).get(model),first)
            replacement=root/'replacement';replacement.write_bytes(b'modified')
            os.utime(replacement,ns=(before.st_atime_ns,before.st_mtime_ns));os.replace(replacement,model)
            second=FileFingerprintCache(index).get(model)
            self.assertNotEqual(first['sha256'],second['sha256'])
            self.assertEqual(second['sha256'],hashlib.sha256(b'modified').hexdigest())

    def test_corruption_and_changes_during_hashing_are_handled(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);model=root/'model';index=root/'hashes.json'
            index.write_text('{broken');model.write_bytes(b'old')
            real=hashlib.file_digest;calls=[]
            def changing(stream, algorithm):
                result=real(stream,algorithm);calls.append(1)
                if len(calls)==1:model.write_bytes(b'new data')
                return result
            with patch('core.file_fingerprints.hashlib.file_digest',side_effect=changing):
                result=FileFingerprintCache(index).get(model)
            self.assertEqual(len(calls),2)
            self.assertEqual(result['sha256'],hashlib.sha256(b'new data').hexdigest())


class TensorFingerprintTests(unittest.TestCase):
    def test_reuse_alias_mutation_and_prefix_identity(self):
        cache=TensorFingerprintCache();value=torch.arange(8).float();writes=[]
        def feed(prefix=b''):
            digest=hashlib.sha256(prefix)
            def write(target):writes.append(1);target.update(value.numpy().tobytes())
            return cache.feed(digest,value,'test',write).hexdigest()
        first=feed();self.assertEqual(feed(),first);self.assertEqual(len(writes),1)
        self.assertNotEqual(feed(b'other'),first);self.assertEqual(len(writes),2)
        value.view(-1)[0]=9
        self.assertNotEqual(feed(),first);self.assertEqual(len(writes),3)
        reference=weakref.ref(value);del value;gc.collect();self.assertIsNone(reference())

    def test_inference_tensors_are_always_rechecked_and_cache_is_bounded(self):
        cache=TensorFingerprintCache(limit=2);writes=[]
        with torch.inference_mode():
            value=torch.ones(2)
            for _ in range(2):
                cache.feed(hashlib.sha256(),value,'test',lambda h:writes.append(1))
        self.assertEqual(len(writes),2)
        values=[torch.ones(2) for _ in range(3)]
        for value in values:cache.feed(hashlib.sha256(),value,'test',lambda h:h.update(b'data'))
        self.assertEqual(len(cache.entries),2)

    def test_hashes_match_previous_byte_representation(self):
        for value in [torch.arange(12).reshape(3,4).float(),torch.arange(12).reshape(3,4).T,
                      torch.ones(3,dtype=torch.bfloat16)]:
            expected=hashlib.sha256()
            cpu=value.detach().cpu().contiguous()
            expected.update(str((tuple(cpu.shape),cpu.dtype)).encode())
            expected.update(cpu.float().numpy().tobytes())
            self.assertEqual(fingerprint_value(value),expected.hexdigest())
            self.assertEqual(fingerprint_value(value),expected.hexdigest())
            native=hashlib.sha256();native.update(str((tuple(cpu.shape),cpu.dtype)).encode())
            native.update(cpu.reshape(-1).view(torch.uint8).numpy().tobytes())
            self.assertEqual(_input_key(value,hashlib.sha256()).hexdigest(),native.hexdigest())
            self.assertEqual(_input_key(value,hashlib.sha256()).hexdigest(),native.hexdigest())


if __name__=='__main__':unittest.main()
