"""Project checkpoints and named shot models for the shared Director."""
from __future__ import annotations
try:
    from ..core.cache_manager import ProjectCacheManager
except ImportError:
    from core.cache_manager import ProjectCacheManager

CATEGORY = "ComfyUI-AhmedAhmedEG"


class MiniMaxH3ModelOverridePack:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"name": ("STRING", {"default": "shot_model"}), "model": ("MODEL",)},
                "optional": {"previous": ("MMX_MODEL_PACK",)}}
    RETURN_TYPES = ("MMX_MODEL_PACK",)
    FUNCTION = "build"
    CATEGORY = CATEGORY

    def build(self, name, model, previous=None):
        if not name.strip(): raise ValueError("Model override name is required.")
        return ({**(previous or {}), name.strip(): model},)


class MiniMaxH3Checkpoint:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"project_id": ("STRING", {"default": "default_director"}),
                "clip_id": ("STRING", {"default": "clip_1"}), "take_id": ("STRING", {"default": "latest"})}}
    RETURN_TYPES = ("MMX_CONTINUATION", "IMAGE", "AUDIO", "LATENT")
    RETURN_NAMES = ("checkpoint", "frames", "audio", "latent")
    FUNCTION = "load"
    CATEGORY = CATEGORY
    @classmethod
    def IS_CHANGED(cls, project_id, clip_id, take_id="latest"):
        manager = ProjectCacheManager(project_id)
        if take_id != "latest": return take_id
        import os
        return os.path.getmtime(manager.get_clip_latent_path(clip_id))

    def load(self, project_id, clip_id, take_id="latest"):
        manager = ProjectCacheManager(project_id)
        if take_id != "latest":
            take = manager._manifest.get("takes", {}).get(take_id)
            if take is None or take.get("clip_id") != clip_id:
                raise ValueError("Selected take does not belong to this project/shot.")
            manager._manifest["clips"][clip_id] = take
        latent = manager.load_clip_latent(clip_id)
        frames = manager.load_clip_frames(clip_id)
        audio = manager.load_clip_audio(clip_id)
        if latent is None or frames is None or audio is None:
            raise ValueError("Selected checkpoint is missing or unreadable.")
        return ({"project_id": project_id, "clip_id": clip_id, "take_id": manager._manifest["clips"][clip_id].get("generation"), "latent": latent,
            "frames": frames, "audio": audio}, frames, audio, latent)


class MiniMaxH3AdvanceCheckpoint:
    """A graph gate makes advancing a staged take explicit and reproducible."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"current": ("MMX_CONTINUATION",), "staged": ("MMX_CONTINUATION",),
            "advance": ("BOOLEAN", {"default": False})}}
    RETURN_TYPES = ("MMX_CONTINUATION",)
    FUNCTION = "choose"
    CATEGORY = CATEGORY

    def choose(self, current, staged, advance=False):
        return (staged if advance else current,)
