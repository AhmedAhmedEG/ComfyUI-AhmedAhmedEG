"""Extract tail video frames and audio from sampled MiniMax H3 joint AV latents."""

from __future__ import annotations

import torch
try:
    from ..core.config import FPS, align_frame_count
    from ..core.executor import decode_video_latent, decode_audio_latent
except (ImportError, ValueError):
    from core.config import FPS, align_frame_count
    from core.executor import decode_video_latent, decode_audio_latent

CATEGORY = "ComfyUI-AhmedAhmedEG"


class MiniMaxH3TailFromLatent:
    """Decodes sampled H3 AV latents and extracts the final tail and last frame for downstream reference."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "samples": ("LATENT",),
                "video_vae": ("VAE",),
                "audio_vae": ("VAE",),
                "tail_seconds": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 15.0, "step": 0.1}),
                "align_to_h3_grid": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("IMAGE", "AUDIO", "IMAGE", "INT", "FLOAT")
    RETURN_NAMES = ("tail_video", "tail_audio", "last_frame", "frame_count", "duration_seconds")
    FUNCTION = "extract"
    CATEGORY = CATEGORY

    def extract(self, samples, video_vae, audio_vae, tail_seconds: float, align_to_h3_grid: bool):
        s = samples["samples"]
        streams = list(s.unbind() if hasattr(s, "unbind") else s)
        video_latent = streams[0]
        audio_latent = streams[1]

        frames = decode_video_latent(video_vae, video_latent)
        audio = decode_audio_latent(audio_vae, audio_latent)

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
