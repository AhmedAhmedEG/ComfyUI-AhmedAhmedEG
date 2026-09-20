"""Extract tail video frames and audio from sampled MiniMax H3 joint AV latents."""

from __future__ import annotations

import torch
try:
    from core.config import FPS, align_frame_count
    from core.executor import decode_video_latent, decode_audio_latent
    from core.continuity import unpack_av_samples
except (ImportError, ValueError):
    from ..core.config import FPS, align_frame_count
    from ..core.executor import decode_video_latent, decode_audio_latent
    from ..core.continuity import unpack_av_samples

CATEGORY = "ComfyUI-AhmedAhmedEG"


class MiniMaxH3TailFromLatent:
    """Decodes sampled H3 AV latents and extracts the final tail and last frame for downstream reference."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "samples": ("LATENT",),
                "vae": ("VAE", {"tooltip": "MiniMax H3 video VAE"}),
                "audio_vae": ("VAE", {"tooltip": "MiniMax H3 audio VAE"}),
                "tail_seconds": ("FLOAT", {"default": 0.5, "min": 0.1, "max": 15.0, "step": 0.05}),
                "align_to_h3_grid": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "video_vae": ("VAE", {"tooltip": "Alias for vae"}),
            },
        }

    RETURN_TYPES = ("IMAGE", "AUDIO", "IMAGE", "INT", "FLOAT")
    RETURN_NAMES = ("ref_video", "ref_video_audio", "last_frame", "frame_count", "duration_seconds")
    FUNCTION = "extract"
    CATEGORY = CATEGORY

    def extract(self, samples, vae=None, audio_vae=None, tail_seconds: float = 0.5, align_to_h3_grid: bool = True, video_vae=None, **kwargs):
        active_video_vae = video_vae if video_vae is not None else vae
        if active_video_vae is None:
            raise ValueError("MiniMaxH3TailFromLatent: vae (video VAE) is required.")

        s = samples["samples"]
        streams, _ = unpack_av_samples(s)
        video_latent = streams[0]
        audio_latent = streams[1] if len(streams) > 1 else torch.zeros((1, 32, 2, max(1, round(video_latent.shape[2] * 40 / 24))), device=video_latent.device, dtype=video_latent.dtype)

        frames = decode_video_latent(active_video_vae, video_latent)
        audio = decode_audio_latent(audio_vae, audio_latent) if audio_vae else {"waveform": torch.zeros((1, 2, 48000)), "sample_rate": 48000}

        total_frames = int(frames.shape[0])
        wanted = max(1, min(total_frames, int(round(tail_seconds * FPS))))

        if align_to_h3_grid:
            count = align_frame_count(wanted, mode="nearest")
            if count > total_frames:
                count = align_frame_count(total_frames, mode="down")
        else:
            count = wanted

        duration = count / FPS

        # Slice audio tail
        wf = audio["waveform"]
        sr = int(audio["sample_rate"])
        audio_samples_wanted = min(wf.shape[-1], int(round(duration * sr)))
        audio_tail = {"waveform": wf[..., -audio_samples_wanted:], "sample_rate": sr}

        tail_frames = frames[-count:]
        last_frame = frames[-1:].clone()

        return (tail_frames, audio_tail, last_frame, count, float(duration))
