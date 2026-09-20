"""Built-in Video Combine and Audio Muxer for MiniMax H3."""

from __future__ import annotations

import datetime
import json
import logging
import os
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Tuple, Union

log = logging.getLogger("MiniMaxH3VideoCombine")

try:
    import folder_paths
except ImportError:
    folder_paths = None

try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_PATH = shutil.which("ffmpeg")

DEPLOY_CODECS_MAP = {
    "Auto": "libx264",
    "H.264": "libx264",
    "H.265": "libx265",
    "VP9": "libvpx-vp9",
    "AV1": "libsvtav1",
}


def resolve_output_path(prefix: str, container: str = "mp4") -> Tuple[str, str, str]:
    now = datetime.datetime.now()
    resolved = prefix
    resolved = resolved.replace("%date:yyyy-MM-dd%", now.strftime("%Y-%m-%d"))
    resolved = resolved.replace("%date:hhmmss%", now.strftime("%H%M%S"))
    resolved = resolved.replace("%date:yyyy%", now.strftime("%Y"))
    resolved = resolved.replace("%date:MM%", now.strftime("%m"))
    resolved = resolved.replace("%date:dd%", now.strftime("%d"))
    resolved = resolved.replace("%date:hh%", now.strftime("%H"))
    resolved = resolved.replace("%date:mm%", now.strftime("%M"))
    resolved = resolved.replace("%date:ss%", now.strftime("%S"))

    if folder_paths and hasattr(folder_paths, "get_output_directory"):
        base_dir = folder_paths.get_output_directory()
    else:
        base_dir = "output"

    full_path = os.path.join(base_dir, resolved)
    dir_name = os.path.dirname(full_path)
    base_name = os.path.basename(full_path) or f"minimax_{now.strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(dir_name, exist_ok=True)

    ext = container.lower().lstrip(".")
    if ext == "auto":
        ext = "mp4"

    final_filename = f"{base_name}.{ext}"
    final_filepath = os.path.join(dir_name, final_filename)

    counter = 1
    while os.path.exists(final_filepath):
        final_filename = f"{base_name}_{counter:04d}.{ext}"
        final_filepath = os.path.join(dir_name, final_filename)
        counter += 1

    subfolder = os.path.relpath(dir_name, base_dir)
    if subfolder == ".":
        subfolder = ""

    return final_filepath, final_filename, subfolder


class MiniMaxH3VideoCombine:
    """Unified Video Combine & Audio Muxer with full DaSiWa compatibility."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "frame_rate": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 120.0, "step": 0.1}),
                "codec": (["Auto", "H.264", "H.265", "VP9", "AV1"], {"default": "Auto"}),
                "container": (["Auto", "mp4", "mkv", "webm"], {"default": "Auto"}),
                "bit_depth": (["Auto", "8-bit", "10-bit"], {"default": "Auto"}),
                "quality": ("INT", {"default": 21, "min": 0, "max": 51, "step": 1}),
                "log_level": (["Standard", "Quiet", "Verbose"], {"default": "Standard"}),
                "pingpong": ("BOOLEAN", {"default": False}),
                "save_metadata": ("BOOLEAN", {"default": True}),
                "filename_prefix": ("STRING", {"default": "video/%date:yyyy-MM-dd%/%date:hhmmss%"}),
                "save_output": ("BOOLEAN", {"default": True}),
                "pass_frames": ("BOOLEAN", {"default": False}),
                "crop_to_audio": ("BOOLEAN", {"default": False}),
                "audio_codec": (["Auto", "aac", "mp3", "flac"], {"default": "Auto"}),
                "audio_bitrate": (["Auto", "128k", "192k", "256k", "320k"], {"default": "192k"}),
                "save_first_frame": ("BOOLEAN", {"default": False}),
                "save_last_frame": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "audio": ("AUDIO",),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
                "unique_id": "UNIQUE_ID",
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("frames", "filename")
    OUTPUT_NODE = True
    FUNCTION = "combine_video"
    CATEGORY = "ComfyUI-AhmedAhmedEG"

    def combine_video(
        self,
        images,
        frame_rate=24.0,
        codec="Auto",
        container="Auto",
        bit_depth="Auto",
        quality=21,
        log_level="Standard",
        pingpong=False,
        save_metadata=True,
        filename_prefix="video/%date:yyyy-MM-dd%/%date:hhmmss%",
        save_output=True,
        pass_frames=False,
        crop_to_audio=False,
        audio_codec="Auto",
        audio_bitrate="192k",
        save_first_frame=False,
        save_last_frame=False,
        audio=None,
        prompt=None,
        extra_pnginfo=None,
        unique_id=None,
    ):
        import torch
        import numpy as np

        if pingpong and len(images) > 1:
            images = torch.cat([images, images.flip(0)[1:-1]], dim=0)

        out_filepath, out_filename, subfolder = resolve_output_path(filename_prefix, container)

        fps = float(frame_rate)
        if fps <= 0:
            fps = 24.0

        num_frames, height, width, channels = images.shape

        ffmpeg = FFMPEG_PATH or shutil.which("ffmpeg")
        if not ffmpeg:
            log.warning("ffmpeg binary not found. Saving frames only.")
            return {"ui": {"images": []}, "result": (images, out_filepath)}

        vcodec = DEPLOY_CODECS_MAP.get(codec, "libx264")
        pix_fmt = "yuv420p10le" if bit_depth == "10-bit" else "yuv420p"

        cmd = [
            ffmpeg,
            "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{width}x{height}",
            "-pix_fmt", "rgb24",
            "-r", str(fps),
            "-i", "-",
        ]

        audio_tmp = None
        if audio is not None and isinstance(audio, dict):
            try:
                waveform = audio.get("waveform")
                sample_rate = int(audio.get("sample_rate", 44100))
                if waveform is not None:
                    audio_tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                    audio_tmp.close()
                    try:
                        import torchaudio
                        if waveform.dim() == 3:
                            waveform = waveform.squeeze(0)
                        if waveform.dim() == 1:
                            waveform = waveform.unsqueeze(0)
                        torchaudio.save(audio_tmp.name, waveform.detach().cpu(), sample_rate)
                    except Exception:
                        import scipy.io.wavfile as wavfile
                        arr = (waveform.detach().squeeze().cpu().float().clamp(-1.0, 1.0).numpy() * 32767.0).astype(np.int16)
                        wavfile.write(audio_tmp.name, sample_rate, arr)

                    cmd.extend(["-i", audio_tmp.name])
                    ac = "aac" if audio_codec == "Auto" else audio_codec.lower()
                    cmd.extend(["-c:a", ac, "-b:a", audio_bitrate])
                    if crop_to_audio:
                        cmd.append("-shortest")
            except Exception as e_aud:
                log.warning(f"Failed to encode audio track: {e_aud}")

        cmd.extend([
            "-c:v", vcodec,
            "-crf", str(quality),
            "-pix_fmt", pix_fmt,
            out_filepath,
        ])

        try:
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            img_bytes = (images.detach().cpu().float().clamp(0.0, 1.0).numpy() * 255.0).astype(np.uint8).tobytes()
            p.communicate(input=img_bytes)
        except Exception as exc:
            log.error(f"ffmpeg execution error: {exc}")
        finally:
            if audio_tmp and os.path.exists(audio_tmp.name):
                try:
                    os.unlink(audio_tmp.name)
                except Exception:
                    pass

        res_frames = images if pass_frames else images[:1]
        ui_res = {
            "video": [{
                "filename": out_filename,
                "subfolder": subfolder,
                "type": "output",
                "format": "video/mp4",
            }]
        }

        return {"ui": ui_res, "result": (res_frames, out_filepath)}
