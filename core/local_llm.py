"""Optional local Prompt Forge providers; weights are loaded from local folders."""
import base64
import io
from pathlib import Path
import threading

from .forge_jobs import stopping_options

_CACHE = {}
_LOCK = threading.RLock()


def model_names():
    import folder_paths
    root = Path(folder_paths.models_dir) / "LLM"
    if not root.is_dir(): return ["Place a model in models/LLM"]
    return sorted(path.name for path in root.iterdir() if path.is_dir() or path.suffix.lower() == ".gguf") or ["Place a model in models/LLM"]


def _load_local_provider(name, backend="transformers", vision=False, device="cpu", projection="", context_length=8192):
    import folder_paths
    root = (Path(folder_paths.models_dir)/"LLM").resolve()
    path = (root/name).resolve()
    if root not in path.parents or not path.exists(): raise ValueError("Select an existing local model in models/LLM.")
    key = (str(path), backend, vision, device, projection, context_length, path.stat().st_mtime_ns)
    with _LOCK:
        if key in _CACHE: return _CACHE[key]
        for cached in _CACHE.values():
            release=getattr(cached,'release',None)
            if callable(release):release()
        _CACHE.clear()
        cached=None
        release=None
        if backend == "gguf":
            try:
                from llama_cpp import Llama
            except ImportError as exc:
                raise RuntimeError("Local GGUF Prompt Forge needs llama-cpp-python.") from exc
            handler = None
            if vision:
                from llama_cpp.llama_chat_format import Llava15ChatHandler
                proj = (root/projection).resolve()
                if root not in proj.parents or not proj.is_file(): raise ValueError("Select a local GGUF vision projection file.")
                handler = Llava15ChatHandler(clip_model_path=str(proj))
            model = Llama(model_path=str(path), n_ctx=int(context_length), n_gpu_layers=-1 if device == "cuda" else 0, chat_handler=handler, verbose=False)
            def generate(messages, max_new_tokens=2048, images=None, temperature=.4, job=None):
                if images:
                    messages = [*messages[:-1], {"role":"user", "content":[{"type":"text", "text":messages[-1]["content"]},
                        *[{"type":"image_url", "image_url":{"url":"data:image/png;base64,"+value}} for value in images]]}]
                if job:
                    job.check();iterator=model.create_chat_completion(messages=messages,max_tokens=max_new_tokens,temperature=temperature,stream=True)
                    try:
                        parts=[]
                        for row in iterator:
                            job.check();parts.append((row.get('choices') or [{}])[0].get('delta',{}).get('content') or '')
                        return ''.join(parts)
                    finally:
                        close=getattr(iterator,'close',None)
                        if callable(close):close()
                result = model.create_chat_completion(messages=messages, max_tokens=max_new_tokens, temperature=temperature)
                return result["choices"][0]["message"]["content"]
        elif backend == "transformers":
            try:
                from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
            except ImportError as exc:
                raise RuntimeError("Local Prompt Forge needs transformers and accelerate.") from exc
            if not path.is_dir(): raise ValueError("Transformers models need a complete local model directory.")
            if vision:
                from transformers import AutoModelForImageTextToText, AutoProcessor
                model = AutoModelForImageTextToText.from_pretrained(str(path), local_files_only=True, dtype="auto")
                processor = AutoProcessor.from_pretrained(str(path), local_files_only=True)
                model = model.to(device)
                def generate(messages, max_new_tokens=2048, images=None, temperature=.4, job=None):
                    from PIL import Image
                    pil = [Image.open(io.BytesIO(base64.b64decode(value))).convert("RGB") for value in images or []]
                    messages = [*messages[:-1], {"role":"user", "content":[*[{"type":"image","image":image} for image in pil], {"type":"text","text":messages[-1]["content"]}]}]
                    inputs = processor.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors="pt").to(device)
                    result = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=temperature>0, temperature=max(temperature,.01), **stopping_options(job,"transformers"))
                    return processor.batch_decode(result[:,inputs["input_ids"].shape[-1]:], skip_special_tokens=True)[0]
            else:
                model = AutoModelForCausalLM.from_pretrained(str(path), local_files_only=True, dtype="auto")
                tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True)
                pipe = pipeline("text-generation", model=model, tokenizer=tokenizer, device=device)
                def generate(messages, max_new_tokens=2048, images=None, temperature=.4, job=None):
                    if images: raise ValueError("The selected local provider is text-only; choose a vision model.")
                    result = pipe(messages, max_new_tokens=max_new_tokens, do_sample=temperature>0, temperature=max(temperature,.01), **stopping_options(job,"transformers"))
                    text = result[0]["generated_text"]
                    return text[-1]["content"] if isinstance(text,list) else text
        else: raise ValueError("Local backend must be transformers or gguf.")
        generation_lock = threading.RLock()
        def serialized_generate(*args, **kwargs):
            with generation_lock:
                return generate(*args, **kwargs)
        def release():
            if backend == "gguf":
                close=getattr(model,"close",None)
                if callable(close): close()
            else:
                model.to("cpu")
        serialized_generate.release=release
        _CACHE.clear()
        _CACHE[key] = serialized_generate
        return serialized_generate


class LocalProvider:
    """Graph-held handle never retains weights after an unload-policy draft."""
    supports_cancel=True

    def __init__(self, options, lifetime):
        if lifetime not in ('unload_after_draft','keep_loaded'): raise ValueError('Unknown prompt model lifetime.')
        self.options=options
        self.lifetime=lifetime

    def __call__(self, *args, **kwargs):
        with _LOCK:
            job=kwargs.get("job")
            if job:job.check()
            generator=_load_local_provider(**self.options)
            try:
                return generator(*args, **kwargs)
            finally:
                if self.lifetime=='unload_after_draft':
                    try: generator.release()
                    finally:
                        _CACHE.clear()
                        del generator
                        import gc
                        gc.collect()
                        try:
                            import torch
                            if torch.cuda.is_available(): torch.cuda.empty_cache()
                        except ImportError: pass


def local_provider(name, backend="transformers", vision=False, device="cpu", projection="", context_length=8192, lifetime="unload_after_draft"):
    return LocalProvider(dict(name=name,backend=backend,vision=vision,device=device,projection=projection,context_length=context_length),lifetime)
