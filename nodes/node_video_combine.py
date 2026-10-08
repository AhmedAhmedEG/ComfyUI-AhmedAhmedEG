"""Built-in Video Combine and Audio Muxer for MiniMax H3."""

from __future__ import annotations

import datetime
import json
import logging
import os
import shutil
import subprocess
import tempfile
from typing import Tuple

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


def resolve_output_path(prefix: str, container: str = "mp4", save_output=True) -> Tuple[str, str, str]:
    if any(ord(char) < 32 for char in prefix): raise ValueError("Output prefix contains control characters.")
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

    if folder_paths:
        base_dir = folder_paths.get_output_directory() if save_output else folder_paths.get_temp_directory()
    else:
        base_dir = "output" if save_output else os.path.join("output", "temp")

    base_dir = os.path.realpath(base_dir)
    full_path = os.path.realpath(os.path.join(base_dir, resolved))
    try:
        contained = os.path.normcase(os.path.commonpath((base_dir, full_path))) == os.path.normcase(base_dir)
    except ValueError:
        contained = False
    if not contained:
        raise ValueError("Video filename prefix must stay inside the output directory.")
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
                "container": (["Auto", "mp4", "mkv", "webm", "Animated WebP", "Animated AVIF"], {"default": "Auto"}),
                "encoder_backend": (["pyav", "ffmpeg"], {"default": "pyav"}),
                "bit_depth": (["Auto", "8-bit", "10-bit"], {"default": "Auto"}),
                "quality": ("INT", {"default": 21, "min": 0, "max": 51, "step": 1}),
                "log_level": (["Standard", "Quiet", "Verbose"], {"default": "Standard"}),
                "pingpong": ("BOOLEAN", {"default": False}),
                "save_metadata": ("BOOLEAN", {"default": True}),
                "filename_prefix": ("STRING", {"default": "video/%date:yyyy-MM-dd%/%date:hhmmss%"}),
                "save_output": ("BOOLEAN", {"default": True}),
                "pass_frames": ("BOOLEAN", {"default": False}),
                "crop_to_audio": ("BOOLEAN", {"default": False}),
                "audio_codec": (["Auto", "aac", "opus", "mp3", "flac"], {"default": "Auto"}),
                "audio_bitrate": (["Auto", "128k", "192k", "256k", "320k"], {"default": "192k"}),
                "save_first_frame": ("BOOLEAN", {"default": False}),
                "save_last_frame": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "audio": ("AUDIO",),
                "seed": ("INT", {"forceInput": True}),
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
        encoder_backend="pyav", seed=None,
    ):
        import torch
        import numpy as np

        if encoder_backend == "pyav":
            if container == "Auto": target_container = "Auto"
            else: target_container = {"mp4":"MP4", "webm":"WebM", "mkv":"MKV"}.get(container.lower(), container)
            try:
                from ..core.vendor.dasiwa.enhanced_video import DaSiWa_EnhancedVideoCombine
            except ImportError:
                from core.vendor.dasiwa.enhanced_video import DaSiWa_EnhancedVideoCombine
            result = DaSiWa_EnhancedVideoCombine().combine(images, frame_rate, "H.265 (HEVC)" if codec == "H.265" else codec,
                target_container, bit_depth, quality, pingpong, save_metadata, filename_prefix,
                save_output, pass_frames, crop_to_audio, audio_codec="Opus" if audio_codec == "opus" else audio_codec.upper() if audio_codec != "Auto" else "Auto",
                audio_bitrate=audio_bitrate, log_level=log_level, save_first_frame=save_first_frame,
                save_last_frame=save_last_frame, audio=audio, seed=seed, prompt=prompt, extra_pnginfo=extra_pnginfo)
            if result["ui"].get("gifs"): result["ui"]["video"] = result["ui"]["gifs"]
            return result
        if encoder_backend != "ffmpeg": raise ValueError("Unknown video encoder backend.")
        if container.startswith("Animated"):
            raise ValueError("Animated output requires the PyAV encoder backend.")

        if pingpong and len(images) > 1:
            images = torch.cat([images, images.flip(0)[1:-1]], dim=0)

        if images.ndim != 4 or images.shape[0] == 0 or images.shape[-1] < 3:
            raise ValueError("Video Combine needs a non-empty RGB IMAGE batch.")
        images = images[..., :3]
        out_filepath, out_filename, subfolder = resolve_output_path(filename_prefix, container, save_output)

        fps = float(frame_rate)
        if fps <= 0:
            fps = 24.0

        num_frames, height, width, channels = images.shape

        ffmpeg = FFMPEG_PATH or shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("ffmpeg is required to save video; install ffmpeg or imageio-ffmpeg.")

        vcodec = DEPLOY_CODECS_MAP.get(codec, "libx264")
        if container.lower() == "webm":
            if codec == "Auto":
                vcodec = "libvpx-vp9"
            elif codec not in ("VP9", "AV1"):
                raise ValueError("WebM requires VP9 or AV1 video.")
        pix_fmt = "yuv420p10le" if bit_depth == "10-bit" else "yuv420p"

        cmd = [
            ffmpeg,
            "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{width}x{height}",
            "-pix_fmt", "rgb48le" if bit_depth == "10-bit" else "rgb24",
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
                    import wave
                    if waveform.ndim == 3:
                        if waveform.shape[0] != 1:
                            raise ValueError("Video Combine supports one audio batch.")
                        waveform = waveform[0]
                    if waveform.ndim == 1:
                        waveform = waveform.unsqueeze(0)
                    arr = (waveform.detach().cpu().float().clamp(-1.0, 1.0).numpy().T * 32767.0).astype('<i2')
                    with wave.open(audio_tmp.name, "wb") as wav:
                        wav.setnchannels(waveform.shape[0])
                        wav.setsampwidth(2)
                        wav.setframerate(sample_rate)
                        wav.writeframes(arr.tobytes())

                    cmd.extend(["-i", audio_tmp.name])
                    ac = ("libopus" if container.lower() == "webm" else "aac") if audio_codec == "Auto" else audio_codec.lower()
                    cmd.extend(["-c:a", ac])
                    if audio_bitrate != "Auto" and ac != "flac":
                        cmd.extend(["-b:a", audio_bitrate])
                    if crop_to_audio:
                        cmd.append("-shortest")
            except Exception:
                if audio_tmp and os.path.exists(audio_tmp.name):
                    os.unlink(audio_tmp.name)
                raise

        if save_metadata:
            cmd.extend(["-metadata", "comment=" + json.dumps({"prompt": prompt, "workflow": extra_pnginfo}, ensure_ascii=False)])
        cmd.extend(["-loglevel", {"Quiet": "error", "Verbose": "verbose"}.get(log_level, "warning")])

        cmd.extend([
            "-c:v", vcodec,
            "-crf", str(quality),
            "-pix_fmt", pix_fmt,
            out_filepath,
        ])

        try:
            with tempfile.TemporaryFile() as errors:
                p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=errors)
                try:
                    for frame in images:
                        pixels = frame.detach().cpu().float().clamp(0.0, 1.0).numpy()
                        p.stdin.write((pixels * (65535. if bit_depth == "10-bit" else 255.)).round().astype('<u2' if bit_depth == "10-bit" else np.uint8).tobytes())
                except BrokenPipeError:
                    pass
                finally:
                    try:
                        p.stdin.close()
                    except BrokenPipeError:
                        pass
                    p.wait()
                errors.seek(0)
                details = errors.read().decode("utf-8", errors="replace")
                if p.returncode != 0:
                    raise RuntimeError(f"ffmpeg failed (exit {p.returncode}): {details[-4000:]}")
            if not os.path.isfile(out_filepath) or os.path.getsize(out_filepath) == 0:
                raise RuntimeError("ffmpeg did not create a video file.")
        finally:
            if audio_tmp and os.path.exists(audio_tmp.name):
                try:
                    os.unlink(audio_tmp.name)
                except Exception:
                    pass

        res_frames = images if pass_frames else images[:1]
        from PIL import Image
        for enabled, index, suffix in ((save_first_frame, 0, "first"), (save_last_frame, -1, "last")):
            if enabled:
                pixels = (images[index].detach().cpu().clamp(0, 1).numpy() * 255).astype(np.uint8)
                Image.fromarray(pixels).save(os.path.splitext(out_filepath)[0] + f"_{suffix}.png")
        ui_res = {
            "video": [{
                "filename": out_filename,
                "subfolder": subfolder,
                "type": "output" if save_output else "temp",
                "format": {".mkv": "video/x-matroska", ".webm": "video/webm"}.get(os.path.splitext(out_filepath)[1], "video/mp4"),
            }]
        }

        return {"ui": ui_res, "result": (res_frames, out_filepath)}
