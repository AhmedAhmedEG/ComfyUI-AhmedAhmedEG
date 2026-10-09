"""ComfyUI MiniMax H3 Master Director package initialization and web routes."""

from __future__ import annotations

import asyncio
import json
import logging
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

__version__ = "1.0.7"
WEB_DIRECTORY = "./web/js"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

log = logging.getLogger("MiniMaxH3MasterDirector")
log.info("MiniMax H3 %s loaded from %s (%d public node types)", __version__, __file__, len(NODE_CLASS_MAPPINGS))
_PREVIEW_LOCKS = weakref.WeakValueDictionary()

# Register server API routes
if getattr(PromptServer, "instance", None) is not None:
    routes = PromptServer.instance.routes

    @routes.get("/minimax_director/status")
    async def package_status(request):
        """Report what this running process loaded, rather than files on disk."""
        return web.json_response({"loaded_version": __version__, "loaded_from": __file__,
            "node_count": len(NODE_CLASS_MAPPINGS), "node_types": list(NODE_CLASS_MAPPINGS),
            "master_types": [name for name in NODE_CLASS_MAPPINGS if "Master" in name]})

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
            from .core.preview import create_preview_plan
            body = await request.json()
            result = await asyncio.to_thread(create_preview_plan, body["timeline"], body.get("scope", "latest"))
            return web.json_response(result)
        except (ValueError, KeyError, TypeError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=503)

    @routes.get("/minimax_director/preview/media")
    async def smart_preview_media(request):
        try:
            from .core.preview import encode_preview, preview_path
            project_id, key = request.query.get("project_id", ""), request.query.get("key", "")
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
        try:
            import folder_paths, base64, io
            from PIL import Image
            from .core.forge import draft_prompts
            from .core.references import load_reference
            body = await request.json()
            state = body["timeline"]
            def create():
                images = []
                ids = body.get("vision_ids", [])
                if len(ids) > 12: raise ValueError("Vision review supports at most 12 references.")
                for rid in ids:
                    row = next((r for r in state.get("references", []) if r["id"] == rid), None)
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
                        bool(images), body.get("device", "cpu"), body.get("projection", ""))
                return draft_prompts(state, body.get("instruction", ""), body.get("count", 1),
                    body.get("backend", "ollama"), body.get("endpoint", "http://localhost:11434"),
                    body.get("model", ""), body.get("api_key", ""), generator=generator, images=images)
            return web.json_response(await asyncio.to_thread(create))
        except (ValueError, TypeError, KeyError, FileNotFoundError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=502)

    @routes.post("/minimax_director/forge/apply")
    async def forge_apply(request):
        try:
            from .core.forge import apply_draft
            body = await request.json()
            return web.json_response({"timeline": apply_draft(body["timeline"], body["draft"], body.get("policy", "replace"))})
        except (ValueError, TypeError, KeyError) as exc:
            return web.json_response({"error": str(exc)}, status=400)

    @routes.post("/minimax_director/project/portable/export")
    async def portable_export(request):
        try:
            import folder_paths, uuid
            from .core.project import write_portable
            body = await request.json()
            mgr = ProjectCacheManager(body.get("project_id", "default"))
            path = os.path.join(mgr.project_dir, "portable_" + uuid.uuid4().hex + ".mmxproj")
            await asyncio.to_thread(write_portable, body["timeline"], folder_paths.get_input_directory(), path)
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
            state = await asyncio.to_thread(read_portable, path, folder_paths.get_input_directory())
            return web.json_response({"timeline": state})
        except (ValueError, TypeError, KeyError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)
        finally:
            if path and os.path.exists(path): os.unlink(path)

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

    @routes.get("/minimax_director/project/takes")
    async def project_takes(request):
        try:
            mgr = ProjectCacheManager(request.query.get("project_id", "default_director"))
            clip_id = request.query.get("clip_id")
            rows = [{"take_id": key, **value} for key, value in mgr._manifest.get("takes", {}).items()
                if clip_id is None or value.get("clip_id") == clip_id]
            return web.json_response(sorted(rows, key=lambda row: row.get("updated_at", 0), reverse=True))
        except ValueError as exc:
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
