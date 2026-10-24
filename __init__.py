"""ComfyUI MiniMax H3 Master Director package initialization and web routes."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
import os
import weakref
try:
    from aiohttp import web
    from server import PromptServer
except Exception:
    web = None
    PromptServer = None

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from .core.refmod import list_available_refmods
from .core.cache_manager import ProjectCacheManager
from .core.media_io import resolve_input_path

__version__ = "1.7.34"
WEB_DIRECTORY = "./web/js"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

log = logging.getLogger("MiniMaxH3MasterDirector")
log.info("MiniMax H3 %s loaded from %s (%d public node types)", __version__, __file__, len(NODE_CLASS_MAPPINGS))
_PREVIEW_LOCKS = weakref.WeakValueDictionary()

# Register server API routes
if getattr(PromptServer, "instance", None) is not None:
    routes = PromptServer.instance.routes

    @web.middleware
    async def release_director_configuration(request, handler):
        # Cooperate with ComfyUI's existing Free Memory/Unload Models controls.
        if request.path in ('/free','/api/free') and request.method == 'POST':
            try:
                body = await request.json()
                if body.get('unload_models') or body.get('free_memory'):
                    from .core.run_resources import _sampling_configuration
                    _sampling_configuration.reset()
            except (ValueError, TypeError, AttributeError): pass
        return await handler(request)

    if isinstance(getattr(PromptServer.instance,'app',None),web.Application):
        PromptServer.instance.app.middlewares.append(release_director_configuration)

    @routes.get("/minimax_director/status")
    async def package_status(request):
        """Report what this running process loaded, rather than files on disk."""
        return web.json_response({"loaded_version": __version__, "loaded_from": __file__,
            "node_count": len(NODE_CLASS_MAPPINGS), "node_types": list(NODE_CLASS_MAPPINGS),
            "master_types": [name for name in NODE_CLASS_MAPPINGS if "Master" in name]})

    @routes.get("/minimax_director/progress")
    async def clip_progress(request):
        from .core.progress import progress_snapshot
        return web.json_response(progress_snapshot(
            request.query.get("node", ""), request.query.get("project_id", ""),
            PromptServer.instance.prompt_queue), headers={'Cache-Control': 'no-store'})

    @routes.get("/minimax_director/hardware")
    async def hardware_stats(request):
        from .core.hardware_monitor import hardware_monitor
        return web.json_response(await asyncio.to_thread(hardware_monitor.snapshot),
            headers={'Cache-Control': 'no-store'})

    @routes.post("/minimax_director/memory/release")
    async def release_vram(request):
        from .core.memory_controls import request_vram_release
        try:
            return web.json_response(request_vram_release(PromptServer.instance.prompt_queue))
        except RuntimeError as exc:
            return web.json_response({'error': str(exc)}, status=409)

    @routes.post("/minimax_director/media/upload")
    async def upload_media(request):
        import tempfile
        temporary = None
        try:
            import folder_paths, hashlib
            from pathlib import Path
            reader = await request.multipart()
            part = await reader.next()
            if part is None or not part.filename: raise ValueError("Choose a media file.")
            suffix = Path(part.filename).suffix.lower()
            if not suffix or len(suffix) > 12 or not suffix[1:].isalnum(): raise ValueError("Media file needs a valid extension.")
            fd, temporary = tempfile.mkstemp(suffix=suffix,dir=folder_paths.get_temp_directory())
            digest = hashlib.sha256(); size = 0
            with os.fdopen(fd,"wb") as output:
                while chunk := await part.read_chunk():
                    size += len(chunk)
                    if size > 8*1024**3: raise ValueError("Media upload exceeds 8 GiB.")
                    digest.update(chunk); output.write(chunk)
            def inspect():
                from PIL import Image
                try:
                    with Image.open(temporary) as image:
                        image.verify()
                    return "image"
                except Exception:
                    import av
                    with av.open(temporary) as container:
                        if container.streams.video: return "video"
                        if container.streams.audio: return "audio"
                    raise ValueError("File contains no supported image/video/audio stream.")
            kind = await asyncio.to_thread(inspect)
            folder = Path(folder_paths.get_input_directory())/"minimax_assets"
            folder.mkdir(parents=True,exist_ok=True)
            name = digest.hexdigest()+suffix
            os.replace(temporary,folder/name); temporary = None
            return web.json_response({"name":name,"subfolder":"minimax_assets","type":"input","media_type":kind})
        except (ValueError,TypeError) as exc:
            return web.json_response({"error":str(exc)},status=400)
        except Exception as exc:
            return web.json_response({"error":str(exc)},status=400)
        finally:
            if temporary and os.path.exists(temporary): os.unlink(temporary)

    @routes.post("/minimax_director/preview/info")
    async def smart_preview_info(request):
        try:
            from .core.preview import create_preview_plan, cached_preview_plan
            from .core.progress import preview_run_context, master_preview_input
            body = await request.json()
            timeline = body['timeline']
            master_state = master_preview_input(timeline['project_id']) if body.get('master_input', False) else None
            if master_state is None:
                result = await asyncio.to_thread(cached_preview_plan, timeline['project_id'],
                    body.get('scope','latest'), quality=body.get('quality','original'),stream=body.get('stream','final'))
                return web.json_response(result, headers={'Cache-Control':'no-store'})
            timeline = master_state
            context = preview_run_context(timeline['project_id'], timeline.get('clips', []),
                PromptServer.instance.prompt_queue, body.get('stream', 'final'))
            result = await asyncio.to_thread(create_preview_plan, timeline, body.get("scope", "latest"),
                quality=body.get("quality", "original"),stream=body.get("stream","final"), run_context=context)
            return web.json_response(result)
        except (ValueError, KeyError, TypeError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=503)

    @routes.get("/minimax_director/preview/segment")
    async def smart_preview_segment(request):
        try:
            from .core.preview import preview_path
            from .core.preview_segments import encode_fragment
            project_id,key=request.query.get('project_id',''),request.query.get('key','')
            from .core.progress import master_preview_input
            if request.query.get('read_only') == '1' or master_preview_input(project_id) is None:
                from .core.cache_manager import get_cache_root_dir, safe_component
                import re
                if not re.fullmatch(r'[0-9a-f]{64}',key): raise ValueError('Invalid preview revision.')
                path=os.path.join(get_cache_root_dir(create=False),safe_component(project_id),'previews',key+'.mp4')
                if not os.path.isfile(path): raise FileNotFoundError('Cached preview is unavailable; waiting for Master output.')
                return web.FileResponse(path,headers={'Content-Type':'video/mp4','Cache-Control':'no-store'})
            preview_path(project_id,key)
            lock=_PREVIEW_LOCKS.setdefault(f'segment:{project_id}:{key}',asyncio.Lock())
            async with lock: path=await asyncio.to_thread(encode_fragment,project_id,key)
            return web.FileResponse(path,headers={'Content-Type':'video/mp4','Cache-Control':'private, max-age=31536000, immutable'})
        except (ValueError,FileNotFoundError) as exc:
            return web.json_response({'error':str(exc)},status=404)
        except Exception as exc:
            return web.json_response({'error':str(exc)},status=503)

    @routes.get("/minimax_director/preview/media")
    async def smart_preview_media(request):
        try:
            from .core.preview import encode_preview, preview_path
            project_id, key = request.query.get("project_id", ""), request.query.get("key", "")
            if request.query.get('download')=='1':
                from .core.preview_export import export_cached_preview
                import tempfile
                # A user-requested export may assemble existing fragments even
                # before Master input. Its temporary file never changes caches.
                with tempfile.TemporaryDirectory(prefix='minimax-preview-export-') as folder:
                    path=await asyncio.to_thread(export_cached_preview,project_id,key,folder)
                    response=web.StreamResponse(headers={'Content-Type':'video/mp4','Cache-Control':'no-store',
                        'Content-Disposition':'attachment; filename="minimax-preview.mp4"',
                        'Content-Length':str(os.path.getsize(path))})
                    await response.prepare(request)
                    with open(path,'rb') as media:
                        while True:
                            chunk=await asyncio.to_thread(media.read,1024*1024)
                            if not chunk:break
                            await response.write(chunk)
                    await response.write_eof()
                    return response
            from .core.progress import master_preview_input
            if request.query.get('read_only') == '1' or master_preview_input(project_id) is None:
                from .core.cache_manager import get_cache_root_dir, safe_component
                import re
                if not re.fullmatch(r'[0-9a-f]{64}',key): raise ValueError('Invalid preview revision.')
                path=os.path.join(get_cache_root_dir(create=False),safe_component(project_id),'previews',key+'.mp4')
                if not os.path.isfile(path): raise FileNotFoundError('Cached preview is unavailable; waiting for Master output.')
                headers={'Content-Type':'video/mp4','Cache-Control':'no-store'}
                if request.query.get('download')=='1': headers['Content-Disposition']='attachment; filename="minimax-preview.mp4"'
                return web.FileResponse(path,headers=headers)
            preview_path(project_id, key)  # Validate before using identifiers as lock keys.
            lock = _PREVIEW_LOCKS.setdefault(f"{project_id}:{key}", asyncio.Lock())
            async with lock:
                path = await asyncio.to_thread(encode_preview, project_id, key)
            headers = {"Content-Type": "video/mp4", "Cache-Control": "private, max-age=31536000, immutable"}
            if request.query.get("download") == "1":
                headers["Content-Disposition"] = 'attachment; filename="minimax-preview.mp4"'
            return web.FileResponse(path, headers=headers)
        except (ValueError, FileNotFoundError) as exc:
            return web.json_response({"error": str(exc)}, status=404)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=503)

    @routes.get("/minimax_director/video/preview")
    async def video_preview(request):
        try:
            import folder_paths, hashlib
            from .core.vendor.dasiwa.helper_pyav_video import transcode_preview
            filename = request.query.get("filename", "")
            kind = request.query.get("type", "output")
            subfolder = request.query.get("subfolder", "")
            if kind not in ("output", "temp") or not filename or filename != os.path.basename(filename):
                raise ValueError("Invalid preview asset.")
            root = folder_paths.get_output_directory() if kind == "output" else folder_paths.get_temp_directory()
            source = resolve_input_path(os.path.join(subfolder, filename), root)
            stat = os.stat(source)
            key = hashlib.sha256(f"{source}:{stat.st_size}:{stat.st_mtime_ns}".encode()).hexdigest()
            folder = os.path.join(folder_paths.get_temp_directory(), "minimax_previews")
            os.makedirs(folder, exist_ok=True)
            target = os.path.join(folder,key+".mp4")
            lock = _PREVIEW_LOCKS.setdefault(key,asyncio.Lock())
            async with lock:
                if not os.path.isfile(target): await asyncio.to_thread(transcode_preview,source,target)
            return web.FileResponse(target,headers={"Content-Type":"video/mp4"})
        except (ValueError,FileNotFoundError) as exc:
            return web.json_response({"error":str(exc)},status=400)
        except Exception as exc:
            return web.json_response({"error":str(exc)},status=503)

    @routes.get("/minimax_director/loras")
    async def get_loras(request):
        try:
            import folder_paths
            return web.json_response(folder_paths.get_filename_list("loras"))
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    @routes.get("/minimax_director/loras/info")
    async def lora_info(request):
        try:
            import folder_paths
            from pathlib import Path
            name = request.query.get("name", "")
            if name not in folder_paths.get_filename_list("loras"):
                raise ValueError("Select an installed LoRA.")
            path = folder_paths.get_full_path("loras", name)
            def inspect():
                from safetensors import safe_open
                with safe_open(path, framework="pt", device="cpu") as source:
                    metadata = source.metadata() or {}
                stem = Path(path).with_suffix("")
                preview = next((str(stem) + ext for ext in (".png", ".jpg", ".webp") if os.path.isfile(str(stem) + ext)), None)
                return {"name": name, "metadata": metadata, "has_preview": bool(preview)}
            result = await asyncio.to_thread(inspect)
            if request.query.get("preview") == "1":
                stem = Path(path).with_suffix("")
                preview = next((str(stem) + ext for ext in (".png", ".jpg", ".webp") if os.path.isfile(str(stem) + ext)), None)
                if preview is None: return web.json_response({"error": "No local preview."}, status=404)
                return web.FileResponse(preview)
            return web.json_response(result)
        except (ValueError, FileNotFoundError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    @routes.get("/minimax_director/media/waveform")
    async def media_waveform(request):
        try:
            import folder_paths
            from .core.media_io import load_audio
            from .core.references import waveform
            def decode():
                audio = load_audio(request.query.get("filename", ""), folder_paths.get_input_directory())
                return {"peaks": waveform(audio), "duration": audio["waveform"].shape[-1] / audio["sample_rate"]}
            return web.json_response(await asyncio.to_thread(decode))
        except (ValueError, FileNotFoundError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    @routes.post("/minimax_director/media/frame")
    async def source_frame(request):
        try:
            import folder_paths, hashlib, math
            from pathlib import Path
            from .core.media_io import load_video
            from PIL import Image
            body = await request.json()
            time = float(body.get("time", 0))
            if not math.isfinite(time) or time < 0: raise ValueError("Frame time must be finite and non-negative.")
            def extract():
                frames = load_video(body["filename"], folder_paths.get_input_directory(), trim_start=time, trim_end=time+1/24, target_fps=24)
                pixels = (frames[0].clamp(0, 1).cpu().numpy() * 255).round().astype("uint8")
                relative = "minimax_frames/" + hashlib.sha256(pixels.tobytes()).hexdigest() + ".png"
                path = Path(folder_paths.get_input_directory()) / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                Image.fromarray(pixels).save(path)
                return {"filename": relative}
            return web.json_response(await asyncio.to_thread(extract))
        except (ValueError, FileNotFoundError, KeyError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    @routes.post("/minimax_director/forge/draft")
    async def forge_draft(request):
        job_id=None
        try:
            queue=PromptServer.instance.prompt_queue
            running,_=queue.get_current_queue()
            if running:raise ValueError('Prompt Forge is unavailable while ComfyUI is generating. Wait for the current run to finish.')
            import folder_paths, base64, io
            from PIL import Image
            from .core.forge import draft_prompts
            from .core.references import load_reference
            body = await request.json()
            from .core.forge_jobs import start_job,finish_job
            job_id,job=start_job(body.get('job_id') or str(uuid.uuid4()))
            state = body["timeline"]
            def create():
                images = []
                ids = body.get("vision_ids", [])
                if len(ids) > 12: raise ValueError("Vision review supports at most 12 references.")
                for rid in ids:
                    row = next((r for r in [*state.get("references", []),*state.get("available_refs", [])] if r["id"] == rid), None)
                    if row is None: raise ValueError(f"Unknown vision reference: {rid}")
                    loaded = load_reference(row, folder_paths.get_input_directory())
                    visual = next((r["data"] for r in loaded if r["type"] in ("image", "video")), None)
                    if visual is None: raise ValueError("Vision review needs an image/video reference.")
                    pixels = (visual[0].clamp(0, 1).cpu().numpy()*255).round().astype("uint8")
                    image = Image.fromarray(pixels); image.thumbnail((1024, 1024))
                    stream = io.BytesIO(); image.save(stream, format="PNG")
                    images.append(base64.b64encode(stream.getvalue()).decode())
                generator = None
                if body.get("backend") == "local":
                    from .core.local_llm import local_provider
                    generator = local_provider(body.get("model", ""), body.get("local_backend", "transformers"),
                        bool(images) or bool(body.get('continuation_clip_id')), body.get("device", "cpu"), body.get("projection", ""),body.get('context_length',8192),body.get('lifetime','unload_after_draft'))
                return draft_prompts(state, body.get("instruction", ""), body.get("count", 1),
                    body.get("backend", "ollama"), body.get("endpoint", "http://localhost:11434"),
                    body.get("model", ""), body.get("api_key", ""), generator=generator, images=images, creativity=body.get("creativity",4), detail=body.get("detail",6), shot_descriptions=body.get("shot_descriptions"),continuation_clip_id=body.get('continuation_clip_id',''),job=job)
            return web.json_response(await asyncio.to_thread(create))
        except asyncio.CancelledError:
            if job_id:
                from .core.forge_jobs import cancel_job
                await asyncio.to_thread(cancel_job,job_id)
            raise
        except (ValueError, TypeError, KeyError, FileNotFoundError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=502)
        finally:
            if job_id:finish_job(job_id)

    @routes.post('/minimax_director/forge/vision')
    async def forge_vision(request):
        job_id = None
        try:
            running, _ = PromptServer.instance.prompt_queue.get_current_queue()
            if running:
                raise ValueError('Wait for the current ComfyUI generation before using the vision reader.')
            body = await request.json()
            from .core.forge_jobs import start_job, finish_job
            from .core.forge import provider_text
            from .core.cast_tools import parse_people, read_cast, image_b64
            from .core.media_io import resolve_input_path
            import folder_paths
            from PIL import Image, ImageOps
            job_id, job = start_job(body.get('job_id') or str(uuid.uuid4()))
            def create():
                generator = None
                if body.get('backend') == 'local':
                    from .core.local_llm import local_provider
                    generator = local_provider(body.get('model', ''), body.get('local_backend', 'transformers'), True,
                        body.get('device', 'cpu'), body.get('projection', ''), body.get('context_length', 8192), body.get('lifetime', 'unload_after_draft'))
                def provider(system, user, images):
                    return provider_text(system, user, body.get('backend', 'ollama'), body.get('endpoint', 'http://localhost:11434'),
                        body.get('model', ''), body.get('api_key', ''), generator, images, 2, job, 2048)
                def load(row):
                    job.check()
                    path = resolve_input_path(row.get('filename', ''), folder_paths.get_input_directory())
                    with Image.open(path) as image:
                        return ImageOps.exif_transpose(image).convert('RGB')
                if body.get('operation') == 'find_people':
                    image = load(body['reference'])
                    text = provider('Locate every visible person. Return JSON only: {"people":[{"label":"short visible description","box":[x1,y1,x2,y2]}]}. '
                        'Coordinates must be fractions from 0 to 1 of the entire image, top-left to bottom-right, with one full-body box per person. Return an empty people array if none are visible.',
                        'Find the people in this image.', [image_b64(image)])
                    return {'boxes': parse_people(text)}
                if body.get('operation') == 'describe':
                    return {'text': read_cast(body['timeline'], body['card_key'], load, provider, body.get('instruction', ''))}
                raise ValueError('Unknown vision operation.')
            return web.json_response(await asyncio.to_thread(create))
        except asyncio.CancelledError:
            if job_id:
                from .core.forge_jobs import cancel_job
                await asyncio.to_thread(cancel_job, job_id)
            raise
        except (ValueError, TypeError, KeyError, FileNotFoundError) as exc:
            return web.json_response({'error': str(exc)}, status=400)
        except Exception as exc:
            return web.json_response({'error': str(exc)}, status=502)
        finally:
            if job_id:
                finish_job(job_id)

    @routes.post('/minimax_director/forge/cancel')
    async def forge_cancel(request):
        from .core.forge_jobs import cancel_job
        body=await request.json()
        return web.json_response({'cancelled':await asyncio.to_thread(cancel_job,body.get('job_id',''))})

    @routes.post('/minimax_director/forge/prepare_history')
    async def forge_prepare_history(request):
        try:
            from .core.forge import prepare_imported_history
            body = await request.json()
            return web.json_response(prepare_imported_history(body['timeline'], body['index']))
        except (ValueError, TypeError, KeyError) as exc:
            return web.json_response({'error': str(exc)}, status=400)

    @routes.post("/minimax_director/forge/apply")
    async def forge_apply(request):
        try:
            from .core.forge import apply_draft
            body = await request.json()
            return web.json_response({"timeline": apply_draft(body["timeline"], body["draft"], body.get("policy", "replace"))})
        except (ValueError, TypeError, KeyError) as exc:
            return web.json_response({"error": str(exc)}, status=400)

    @routes.post("/minimax_director/project/convert")
    async def convert_upstream_project(request):
        try:
            import folder_paths
            from .core.project_conversion import read_conversion
            import tempfile
            reader=await request.multipart();restore_cache=False;got_file=False
            with tempfile.TemporaryDirectory(prefix='h3-import-') as root:
                path=os.path.join(root,'project.upload')
                async for part in reader:
                    if part.filename:
                        if got_file:raise ValueError('Upload one project archive at a time.')
                        got_file=True;size=0
                        with open(path,'wb') as dest:
                            while chunk:=await part.read_chunk():
                                size+=len(chunk)
                                if size>8*1024**3:raise ValueError('Project archive exceeds 8 GiB.')
                                dest.write(chunk)
                    elif part.name=='restore_cache':restore_cache=(await part.text())=='true'
                if not got_file:raise ValueError('Choose an upstream project/archive.')
                from .core.transfer import progress_callback
                progress=progress_callback(PromptServer.instance,request.query.get('job_id'))
                state,report=await asyncio.to_thread(read_conversion,path,folder_paths.get_input_directory(),restore_cache=restore_cache,progress=progress)
            return web.json_response({'timeline':state,'report':report})
        except (ValueError,TypeError,KeyError) as exc:
            return web.json_response({'error':str(exc)},status=400)

    @routes.post("/minimax_director/project/portable/export")
    async def portable_export(request):
        try:
            import folder_paths, uuid
            from .core.project import write_portable
            body = await request.json()
            mgr = ProjectCacheManager(body.get("project_id", "default"))
            path = os.path.join(mgr.project_dir, "portable_" + uuid.uuid4().hex + ".mmxproj")
            from .core.transfer import progress_callback
            progress=progress_callback(PromptServer.instance,request.query.get("job_id"))
            await asyncio.to_thread(write_portable, body["timeline"], folder_paths.get_input_directory(), path,progress)
            return web.FileResponse(path, headers={"Content-Disposition": 'attachment; filename="MiniMaxProject.mmxproj"'})
        except (ValueError, TypeError, KeyError, FileNotFoundError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    @routes.post("/minimax_director/project/portable/import")
    async def portable_import(request):
        import tempfile
        path = None
        try:
            import folder_paths
            from .core.project import read_portable
            reader = await request.multipart()
            part = await reader.next()
            if part is None: raise ValueError("No archive uploaded.")
            fd, path = tempfile.mkstemp(suffix=".mmxproj", dir=folder_paths.get_temp_directory())
            total = 0
            with os.fdopen(fd, "wb") as output:
                while chunk := await part.read_chunk():
                    total += len(chunk)
                    if total > 8 * 1024**3: raise ValueError("Archive exceeds 8 GiB.")
                    output.write(chunk)
            from .core.transfer import progress_callback
            progress=progress_callback(PromptServer.instance,request.query.get("job_id"))
            state = await asyncio.to_thread(read_portable, path, folder_paths.get_input_directory(),progress=progress)
            return web.json_response({"timeline": state})
        except (ValueError, TypeError, KeyError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)
        finally:
            if path and os.path.exists(path): os.unlink(path)

    @routes.get("/minimax_director/project/list")
    async def list_server_projects(request):
        from .core.project_store import ServerProjectStore
        return web.json_response({"projects": await asyncio.to_thread(ServerProjectStore().list)})

    @routes.get("/minimax_director/project/load")
    async def load_server_project(request):
        from .core.project_store import ServerProjectStore
        try:
            document = await asyncio.to_thread(ServerProjectStore().load, request.query.get("project_id", ""))
            return web.json_response({"project": document})
        except FileNotFoundError:
            return web.json_response({"error": "Saved project not found."}, status=404)
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            return web.json_response({"error": str(exc)}, status=400)

    @routes.post("/minimax_director/project/save")
    async def save_server_project(request):
        from .core.project_store import ServerProjectStore, ProjectConflict
        try:
            body = await request.json()
            project = await asyncio.to_thread(ServerProjectStore().save,
                body["project_id"], body["name"], body["timeline"], body["workflow"],
                body["master_node_id"], body.get("expected_revision"))
            return web.json_response({"project": project})
        except ProjectConflict as exc:
            return web.json_response({"error": str(exc)}, status=409)
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            return web.json_response({"error": str(exc)}, status=400)

    @routes.get("/minimax_director/project/recover")
    async def recover_project(request):
        try:
            from .core.project import migrate_timeline
            mgr = ProjectCacheManager(request.query.get("project_id", "default"))
            def read():
                with open(os.path.join(mgr.project_dir, "autosave.json"), encoding="utf-8") as stream:
                    return migrate_timeline(json.load(stream))
            return web.json_response({"timeline": await asyncio.to_thread(read)})
        except FileNotFoundError:
            return web.json_response({"error": "This project has no saved run."}, status=404)
        except (ValueError, TypeError) as exc:
            return web.json_response({"error": str(exc)}, status=400)

    @routes.get("/minimax_director/project/cache/status")
    async def project_cache_status(request):
        try:
            mgr = ProjectCacheManager(request.query.get("project_id", "default_director"))
            return web.json_response({"project_id": mgr.project_id, "clips": await asyncio.to_thread(mgr.result_availability)})
        except (ValueError, TypeError) as exc:
            return web.json_response({"error": str(exc)}, status=400)

    @routes.post("/minimax_director/project/merge")
    async def merge_project(request):
        try:
            import folder_paths
            from .core.project import merge_timeline, missing_assets
            body = await request.json()
            state = merge_timeline(body.get("current", {}), body["incoming"], body.get("policy", "overwrite"))
            return web.json_response({"timeline": state, "missing": missing_assets(state, folder_paths.get_input_directory())})
        except (ValueError, TypeError, KeyError) as exc:
            return web.json_response({"error": str(exc)}, status=400)

    @routes.get("/minimax_director/source/info")
    async def source_info(request):
        try:
            import folder_paths
            path = resolve_input_path(request.query.get("filename", ""), folder_paths.get_input_directory())
            def inspect():
                import av
                with av.open(path) as container:
                    video = next((s for s in container.streams if s.type == "video"), None)
                    if video is None:
                        raise ValueError("Source file has no video stream.")
                    duration = float(video.duration * video.time_base) if video.duration is not None else float(container.duration or 0) / av.time_base
                    return {"duration": duration, "fps": float(video.average_rate or 24),
                        "width": video.width, "height": video.height,
                        "has_audio": any(s.type == "audio" for s in container.streams)}
            return web.json_response(await asyncio.to_thread(inspect))
        except (ValueError, FileNotFoundError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    @routes.get("/minimax_director/refmods")
    async def get_refmods(request):
        """List all available RefMod safetensors files."""
        try:
            entries = await asyncio.to_thread(list_available_refmods)
            return web.json_response(entries)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    @routes.post("/minimax_director/project/export")
    async def export_project(request):
        """Export lightweight project data (without heavy cached latents)."""
        try:
            body = await request.json()
            project_id = str(body.get("project_id", "default")).strip()
            timeline_state = body.get("timeline", {})
            name = str(body.get("name", "MiniMaxProject")).strip()

            mgr = ProjectCacheManager(project_id)
            timeline_state = {**timeline_state, "project_id": mgr.project_id}
            project_data = await asyncio.to_thread(mgr.export_lightweight_project_data, timeline_state, project_name=name)
            return web.json_response({"ok": True, "project": project_data})
        except (ValueError, TypeError, AttributeError) as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=500)

    @routes.post("/minimax_director/project/import")
    async def import_project(request):
        """Import lightweight project data and reconnect with existing server-side cache."""
        try:
            body = await request.json()
            project_data = body.get("project", {})
            project_id = str(project_data.get("project_id", "default")).strip()

            mgr = ProjectCacheManager(project_id)
            timeline = await asyncio.to_thread(mgr.import_lightweight_project_data, project_data)
            return web.json_response({"ok": True, "timeline": timeline})
        except (ValueError, TypeError, AttributeError) as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=500)

    @routes.post("/minimax_director/project/clear_cache")
    async def clear_cache(request):
        """Clear server-side cache for a given project."""
        try:
            body = await request.json()
            project_id = str(body.get("project_id", "default")).strip()
            mgr = ProjectCacheManager(project_id)
            await asyncio.to_thread(mgr.clear_project_cache)
            return web.json_response({"ok": True})
        except (ValueError, TypeError, AttributeError) as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=500)

    @routes.post("/minimax_director/smart_split")
    async def smart_split(request):
        """Smart shot detection using PySceneDetect for V2V timeline editing."""
        try:
            body = await request.json()
            filename = str(body.get("filename", "")).strip()
            threshold = float(body.get("threshold", 27.0))

            try:
                import folder_paths
                in_dir = folder_paths.get_input_directory()
                video_path = resolve_input_path(filename, in_dir)
            except ImportError:
                return web.json_response({"ok": False, "error": "ComfyUI input directory is unavailable."}, status=503)

            if not os.path.isfile(video_path):
                return web.json_response({"ok": False, "error": "Video file not found."}, status=404)

            def _detect_scenes():
                try:
                    from scenedetect import open_video, SceneManager
                    from scenedetect.detectors import ContentDetector
                    video = open_video(video_path)
                    sm = SceneManager()
                    sm.add_detector(ContentDetector(threshold=threshold))
                    sm.detect_scenes(video)
                    scenes = sm.get_scene_list()
                    return [{"start": s[0].get_seconds(), "end": s[1].get_seconds()} for s in scenes]
                except ImportError:
                    return None

            detected = await asyncio.to_thread(_detect_scenes)
            if detected is None:
                return web.json_response({"ok": False, "error": "scenedetect package not installed on server."}, status=400)

            return web.json_response({"ok": True, "scenes": detected})
        except FileNotFoundError:
            return web.json_response({"ok": False, "error": "Video file not found."}, status=404)
        except (ValueError, TypeError, AttributeError) as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=500)

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
]
