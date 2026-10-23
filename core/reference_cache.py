"""Project RefMod-format reference encodings with a bounded CPU working set."""
from collections import OrderedDict
import hashlib
import json
import os
import tempfile
import re
from contextlib import contextmanager
from pathlib import Path


def _input_key(value, digest):
    import torch
    if isinstance(value, torch.Tensor):
        data = value.detach().cpu().contiguous()
        digest.update(str((tuple(data.shape), data.dtype)).encode())
        raw = memoryview(data.reshape(-1).view(torch.uint8).numpy()).cast('B')
        for offset in range(0, len(raw), 1024**2):
            digest.update(raw[offset:offset + 1024**2])
    elif isinstance(value, dict):
        for key in sorted(value):
            _input_key(key, digest); _input_key(value[key], digest)
    elif isinstance(value, (list, tuple)):
        digest.update(str(type(value)).encode())
        for item in value: _input_key(item, digest)
    elif value is None or isinstance(value, (str, int, float, bool)):
        digest.update(repr(value).encode() + b'\0')
    else:
        raise TypeError('Unsupported reference encode argument')


class ReferenceEncodeCache:
    def __init__(self, limit_bytes=128 * 1024**2):
        self.limit_bytes = limit_bytes
        self.entries = OrderedDict()
        self.bytes = self.hits = self.misses = 0
        self.proxies = {}
        self.folder = None
        self.index = {}
        self.owner = None
        self.active = set()
        self.vae_identities = {}

    def source_key(self, kind, data, audio=None):
        digest=hashlib.sha256();_input_key((kind,data,audio),digest)
        return digest.hexdigest()

    def configure(self, project_dir, sources, signature='1', vaes=()):
        self.folder=Path(project_dir)/'reference_latents'
        self.folder.mkdir(exist_ok=True)
        if self.folder.is_symlink(): raise ValueError('Reference cache must stay inside the project.')
        self.active=set(sources);self.signature=signature
        try: self.index=json.loads((self.folder/'index.json').read_text(encoding='utf-8'))
        except (OSError,ValueError): self.index={}
        if not isinstance(self.index,dict):self.index={}
        identities={self._vae_identity(v) for v in vaes if v is not None}
        for token,entry in list(self.index.items()):
            if not re.fullmatch(r'[0-9a-f]{64}',token) or not isinstance(entry,dict) or not isinstance(entry.get('owners'),list) or any(not isinstance(v,str) for v in entry['owners']) or not (set(entry['owners']) & self.active) or entry.get('signature')!=signature or identities and entry.get('vae') not in identities:
                self.index.pop(token)
            else:
                entry['owners']=sorted(set(entry['owners']) & self.active)
        self._save_index()
        # Delete only our content-addressed safetensors, never original inputs.
        for path in self.folder.iterdir():
            if re.fullmatch(r'[0-9a-f]{64}\.safetensors',path.name) and path.stem not in self.index and not path.is_symlink(): path.unlink(missing_ok=True)

    def _save_index(self):
        fd,path=tempfile.mkstemp(dir=self.folder,suffix='.tmp')
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as out:json.dump(self.index,out)
            os.replace(path,self.folder/'index.json')
        finally:
            if os.path.exists(path):os.unlink(path)

    @contextmanager
    def asset(self, key):
        old=self.owner;self.owner=key if key in self.active else None
        try:yield
        finally:self.owner=old

    def _vae_identity(self, vae):
        if id(vae) not in self.vae_identities:
            from .cache_manager import fingerprint_value
            identity=getattr(vae,'_mmx_provenance',None)
            if not identity:identity={'session':id(vae)}
            patcher=getattr(vae,'patcher',None)
            patches=getattr(patcher,'patches',{})
            if isinstance(patches,dict) and patches:identity={'vae':identity,'patches':getattr(patcher,'patches_uuid',id(patcher))}
            self.vae_identities[id(vae)]=fingerprint_value(identity)
        return self.vae_identities[id(vae)]

    def _add_owner(self, token):
        if self.owner and token in self.index and self.owner not in self.index[token]['owners']:
            self.index[token]['owners'].append(self.owner);self._save_index()

    def wrap(self, vae):
        if vae is None: return None
        key = id(vae)
        if key not in self.proxies:
            self.proxies[key] = _ReferenceVAE(vae, self)
        return self.proxies[key]

    def encode(self, vae, args, kwargs):
        import torch
        from safetensors import SafetensorError
        digest = hashlib.sha256()
        try:
            _input_key((args, kwargs), digest)
        except TypeError:
            return vae.encode(*args, **kwargs)
        key = (self._vae_identity(vae), digest.hexdigest())
        token=hashlib.sha256(repr((getattr(self,'signature','1'),key)).encode()).hexdigest()
        if key in self.entries:
            data, device = self.entries.pop(key)
            self.entries[key] = (data, device)
            self.hits += 1
            self._add_owner(token)
            return data.to(device).clone()
        path=self.folder/(token+'.safetensors') if self.folder else None
        if path and token in self.index and path.is_file() and not path.is_symlink():
            try:
                from .refmod import load_reference_latent
                data,meta=load_reference_latent(str(path))
                if meta.get('cache_key')!=token:raise ValueError('Mismatched reference cache entry')
                self.hits+=1
                self._add_owner(token)
                device=getattr(vae,'output_device','cpu')
                self._retain(key,data,device)
                return data.to(device).clone()
            except (OSError, ValueError, RuntimeError, SafetensorError) as error:
                if isinstance(error, torch.OutOfMemoryError): raise
                self.index.pop(token,None)
        self.misses += 1
        from .stage_progress import stage
        stage(f'{type(getattr(vae, "first_stage_model", vae)).__name__} · loading as needed and encoding reference')
        result = vae.encode(*args, **kwargs)
        if isinstance(result, torch.Tensor):
            self._retain(key,result,result.device)
            if path and self.owner:
                from .refmod import save_reference_latent
                meta={'kind':'audio' if result.ndim<5 else 'image' if result.shape[2]==1 else 'video',
                      'cache_key':token,'native_encode_shape':list(result.shape)}
                save_reference_latent(str(path),result,meta)
                self.index[token]={'owners':sorted({self.owner,*self.index.get(token,{}).get('owners',[])}),
                                   'signature':self.signature,'vae':self._vae_identity(vae)}
                self._save_index()
        return result

    def _retain(self,key,result,device):
        size=result.numel()*result.element_size()
        if size>self.limit_bytes:return
        while self.entries and self.bytes+size>self.limit_bytes:
            _,(old,_)=self.entries.popitem(last=False);self.bytes-=old.numel()*old.element_size()
        self.entries[key]=(result.detach().cpu().clone(),device);self.bytes+=size

    def clear(self):
        self.entries.clear(); self.proxies.clear(); self.bytes = 0


class _ReferenceVAE:
    def __init__(self, vae, cache):
        self._vae, self._cache = vae, cache

    def __getattr__(self, name):
        return getattr(self._vae, name)

    def encode(self, *args, **kwargs):
        return self._cache.encode(self._vae, args, kwargs)
