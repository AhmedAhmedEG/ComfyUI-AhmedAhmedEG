"""Bounded project conditioning files. No persistent model or GPU tensor cache."""
import hashlib
import inspect
import os
from pathlib import Path
import tempfile
import pickle

from .cache_manager import fingerprint_value
from .reference_cache import _input_key
from .provenance import file_provenance
from .stage_progress import cache_event


def supported(value,key=False,path='inputs'):
    import torch
    if isinstance(value,torch.Tensor) or value is None or isinstance(value,(str,int,float,bool)):return
    if key and isinstance(value,(torch.dtype,torch.device)):return
    if isinstance(value,dict):
        for name,item in value.items():supported(name,key,path);supported(item,key,path+'.'+str(name))
    elif isinstance(value,(list,tuple)):
        for index,item in enumerate(value):supported(item,key,path+'['+str(index)+']')
    else:raise TypeError('Unsupported '+type(value).__name__+' at '+path)


def cpu_copy(value):
    import torch
    if isinstance(value,torch.Tensor):return value.detach().cpu().clone()
    if isinstance(value,dict):return {key:cpu_copy(item) for key,item in value.items()}
    if isinstance(value,list):return [cpu_copy(item) for item in value]
    if isinstance(value,tuple):return tuple(cpu_copy(item) for item in value)
    if value is None or isinstance(value,(str,int,float,bool)):return value
    raise TypeError('Unsupported conditioning data')


def framed_key(value,digest):
    """Frame nesting as well as values so different token structures cannot alias."""
    import torch
    if isinstance(value,(torch.dtype,torch.device)):
        digest.update((type(value).__name__+':'+str(value)+'\0').encode())
    elif isinstance(value,dict):
        digest.update(f'dict:{len(value)}:'.encode())
        for key in sorted(value,key=lambda item:(type(item).__name__,repr(item))):
            digest=framed_key(key,digest);digest=framed_key(value[key],digest)
    elif isinstance(value,(list,tuple)):
        digest.update(f'{type(value).__name__}:{len(value)}:'.encode())
        for item in value:digest=framed_key(item,digest)
    else:
        digest.update((('tensor' if isinstance(value,torch.Tensor) else type(value).__name__)+':').encode())
        digest=_input_key(value,digest)
    return digest


class TextConditioningCache:
    def __init__(self,project_dir,limit_bytes=256*1024**2,limit_entries=32):
        self.folder=Path(project_dir)/'text_conditioning'
        self.limit_bytes,self.limit_entries=limit_bytes,limit_entries

    def key(self,encoder,args,kwargs):
        import torch
        patcher=getattr(encoder,'patcher',None)
        if getattr(patcher,'forced_hooks',None) is not None:
            raise TypeError('Scheduled hooks require live encoding')
        options={key:getattr(encoder,key,None) for key in ('layer_idx','use_clip_schedule','tokenizer_options')}
        options['patcher']={key:getattr(patcher,key,None) for key in ('patches','object_patches','model_options')}
        if getattr(encoder,'apply_hooks_to_conds',None) is not None:
            raise TypeError('Conditioning hooks require live encoding')
        supported((args,kwargs,options),key=True)
        sources=set()
        for value in (encoder,getattr(encoder,'cond_stage_model',None)):
            if value is None:continue
            for cls in type(value).__mro__:
                try:path=inspect.getsourcefile(cls)
                except (TypeError,OSError):path=None
                if path and os.path.isfile(path):sources.add(path)
        identity={'encoder':fingerprint_value(encoder),'options':options,'torch':str(torch.__version__),
                  'sources':[file_provenance(path)['sha256'] for path in sorted(sources)]}
        return framed_key((identity,args,kwargs),hashlib.sha256(b'mmx-text-conditioning-v1')).hexdigest()

    def encode(self,encoder,args,kwargs):
        import torch
        try:key=self.key(encoder,args,kwargs)
        except (TypeError,ValueError,OSError,RuntimeError) as error:
            cache_event('Text conditioning','bypass')
            from .stage_progress import cache_reason
            cache_reason('Text conditioning',str(error))
            return encoder.encode_from_tokens_scheduled(*args,**kwargs)
        if self.folder.is_symlink():raise ValueError('Conditioning cache must stay inside its project')
        path=self.folder/(key+'.pt')
        if path.is_file() and not path.is_symlink():
            try:
                result=torch.load(path,map_location='cpu',weights_only=True)
                if not isinstance(result,dict) or result.get('key')!=key:raise ValueError('Conditioning key mismatch')
                supported(result['conditioning']);os.utime(path,None)
                cache_event('Text conditioning','hit')
                return result['conditioning']
            except (OSError,ValueError,TypeError,RuntimeError,EOFError,KeyError,IndexError,pickle.UnpicklingError):pass
        cache_event('Text conditioning','miss')
        result=encoder.encode_from_tokens_scheduled(*args,**kwargs)
        temporary=None
        try:
            supported(result)
            def size(value):
                if isinstance(value,torch.Tensor):return value.numel()*value.element_size()
                if isinstance(value,dict):return sum(size(v) for v in value.values())
                if isinstance(value,(list,tuple)):return sum(map(size,value))
                return 0
            if size(result)>self.limit_bytes:return result
            self.folder.mkdir(parents=True,exist_ok=True)
            fd,temporary=tempfile.mkstemp(dir=self.folder,suffix='.tmp');os.close(fd)
            torch.save({'key':key,'conditioning':cpu_copy(result)},temporary);os.replace(temporary,path)
            rows=sorted((p for p in self.folder.glob('*.pt') if not p.is_symlink()
                         and len(p.stem)==64 and all(c in '0123456789abcdef' for c in p.stem)),key=lambda p:p.stat().st_mtime_ns)
            total=sum(p.stat().st_size for p in rows)
            while rows and (len(rows)>self.limit_entries or total>self.limit_bytes):
                old=rows.pop(0);total-=old.stat().st_size;old.unlink()
        except (OSError,TypeError):pass
        finally:
            try:
                if temporary and os.path.exists(temporary):os.unlink(temporary)
            except OSError:pass
        return result
