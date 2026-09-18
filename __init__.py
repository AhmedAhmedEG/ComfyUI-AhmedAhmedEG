"""ComfyUI MiniMax H3 Master Director package initialization and web routes."""

from __future__ import annotations

import asyncio
import json
import logging
import os
try:
    from aiohttp import web
    from server import PromptServer
except Exception:
    web = None
    PromptServer = None

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from .core.refmod import list_available_refmods
from .core.cache_manager import ProjectCacheManager

__version__ = "1.0.0"
WEB_DIRECTORY = "./web"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

log = logging.getLogger("MiniMaxH3MasterDirector")

# Register server API routes
if getattr(PromptServer, "instance", None) is not None:
    routes = PromptServer.instance.routes

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
            project_data = mgr.export_lightweight_project_data(timeline_state, project_name=name)
            return web.json_response({"ok": True, "project": project_data})
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
            timeline = mgr.import_lightweight_project_data(project_data)
            return web.json_response({"ok": True, "timeline": timeline})
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
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=500)

    @routes.post("/minimax_director/update")
    async def update_custom_node(request):
        """Self-update the ComfyUI-AhmedAhmedEG custom node from its upstream Git repository."""
        import subprocess
        try:
            repo_dir = os.path.dirname(os.path.abspath(__file__))
            proc = await asyncio.to_thread(
                subprocess.run,
                ["git", "pull", "--no-rebase"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )
            out = proc.stdout.strip()
            err = proc.stderr.strip()
            if proc.returncode == 0:
                msg = out or "Already up to date."
                return web.json_response({"ok": True, "message": msg})
            else:
                return web.json_response({
                    "ok": False,
                    "error": f"Git pull failed (exit code {proc.returncode}):\n{err or out}"
                }, status=500)
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
                video_path = os.path.join(in_dir, filename)
            except Exception:
                video_path = filename

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
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=500)

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
]
