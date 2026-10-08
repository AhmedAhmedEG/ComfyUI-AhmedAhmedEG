"""Native checkpoint loaders add content provenance for persistent resume."""
try:
    from ..core.provenance import record_provenance
except ImportError:
    from core.provenance import record_provenance


class MiniMaxH3ModelLoader:
    @classmethod
    def INPUT_TYPES(cls):
        import folder_paths
        return {"required": {"checkpoint": (folder_paths.get_filename_list("diffusion_models"),),
            "weight_dtype": (["default", "fp8_e4m3fn", "fp8_e4m3fn_fast", "fp8_e5m2"],)}}
    RETURN_TYPES = ("MODEL",)
    FUNCTION = "load"
    CATEGORY = "ComfyUI-AhmedAhmedEG"
    @classmethod
    def IS_CHANGED(cls, checkpoint, weight_dtype="default"):
        import os, folder_paths
        stat = os.stat(folder_paths.get_full_path_or_raise("diffusion_models", checkpoint))
        return stat.st_size, stat.st_mtime_ns

    def load(self, checkpoint, weight_dtype="default"):
        import folder_paths
        from nodes import UNETLoader
        model, = UNETLoader().load_unet(checkpoint, weight_dtype)
        return (record_provenance(model, folder_paths.get_full_path_or_raise("diffusion_models", checkpoint), weight_dtype=weight_dtype),)


class MiniMaxH3EncoderLoader:
    @classmethod
    def INPUT_TYPES(cls):
        import folder_paths
        return {"required": {"text_encoder": (folder_paths.get_filename_list("text_encoders"),),
            "video_vae": (folder_paths.get_filename_list("vae"),), "audio_vae": (folder_paths.get_filename_list("vae"),),
            "device": (["default", "cpu"],)}}
    RETURN_TYPES = ("CLIP", "VAE", "VAE")
    RETURN_NAMES = ("clip", "video_vae", "audio_vae")
    FUNCTION = "load"
    CATEGORY = "ComfyUI-AhmedAhmedEG"
    @classmethod
    def IS_CHANGED(cls, text_encoder, video_vae, audio_vae, device="default"):
        import os, folder_paths
        return tuple((os.stat(folder_paths.get_full_path_or_raise(category, name)).st_size,
            os.stat(folder_paths.get_full_path_or_raise(category, name)).st_mtime_ns)
            for category, name in [("text_encoders", text_encoder), ("vae", video_vae), ("vae", audio_vae)])

    def load(self, text_encoder, video_vae, audio_vae, device="default"):
        import folder_paths
        from nodes import CLIPLoader, VAELoader
        clip, = CLIPLoader().load_clip(text_encoder, "minimax", device)
        video, = VAELoader().load_vae(video_vae)
        audio, = VAELoader().load_vae(audio_vae)
        record_provenance(clip, folder_paths.get_full_path_or_raise("text_encoders", text_encoder), type="minimax", device=device)
        record_provenance(video, folder_paths.get_full_path_or_raise("vae", video_vae))
        record_provenance(audio, folder_paths.get_full_path_or_raise("vae", audio_vae))
        return (clip, video, audio)
