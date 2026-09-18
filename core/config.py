"""Core configuration and constants for MiniMax H3 Master Director."""

from __future__ import annotations

import math
from typing import Tuple

# Frame rate and time standards
FPS = 24.0
AUDIO_LATENT_FPS = 40.0
AUDIO_SAMPLE_RATE = 48000
NATIVE_AUDIO_SAMPLE_RATE = 32000

# MiniMax H3 Temporal Frame Constraint (17k + 5)
# Valid frame lengths include: 5, 22, 39, 56, 73, 90, 107, 124, 141...
MIN_FRAMES = 5
DEFAULT_FRAMES = 124  # approx 5.16 seconds at 24 fps
MAX_FRAMES = 1000

# Context frame options for Motion Context
CONTEXT_FRAME_CHOICES = (5, 22, 39, 56)
DEFAULT_CONTEXT_FRAMES = 22
DEFAULT_AUDIO_CONTEXT_FRAMES = 24

# Spatial resolution constraints
# H3 VAE downsamples by 16; diffusion transformer patchifies 2x2 cells -> 32px multiple required
CANVAS_MULTIPLE = 32
BASE_SHORT_EDGE = 768
MAX_CANVAS_DIMENSION = 4096

# Reference media limits (per official MiniMax H3 specification)
MAX_REF_IMAGES = 9
MAX_REF_VIDEOS = 3
MAX_REF_AUDIOS = 3
MAX_TOTAL_REFS = 12
MIN_REF_DURATION = 2.0  # seconds
MAX_REF_DURATION = 15.0  # seconds
MAX_REF_TOTAL_DURATION = 15.0  # seconds

# Reference image short edge cap
REF_IMAGE_SHORT_EDGE = 2048

# Project format version
PROJECT_FORMAT = "MiniMax H3 Master Director Project"
PROJECT_FORMAT_VERSION = 5


def align_frame_count(n: int, mode: str = "up") -> int:
    """Align frame count to MiniMax H3's required 17k + 5 grid.
    
    mode: 'up' (default), 'down', or 'nearest'
    If n <= 5, returns 5.
    """
    n = max(MIN_FRAMES, int(n))
    rem = (n - 5) % 17
    if rem == 0:
        return n
    if mode == "down":
        return max(MIN_FRAMES, n - rem)
    elif mode == "nearest":
        return max(MIN_FRAMES, n - rem) if rem <= 8 else n + (17 - rem)
    else:  # 'up'
        return n + (17 - rem)


def video_latent_t(frame_count: int) -> int:
    """Compute temporal latent length for a given frame count."""
    fc = align_frame_count(frame_count)
    return 2 if fc <= 5 else ((fc - 5) // 17) * 5 + 2


def audio_latent_length(frame_count: int) -> int:
    """Compute matching audio latent length at 40 Hz."""
    fc = align_frame_count(frame_count)
    return round(fc / FPS * AUDIO_LATENT_FPS)


def snap_to_multiple(val: int | float, multiple: int = CANVAS_MULTIPLE) -> int:
    """Snap a dimension to the nearest multiple (minimum 1 multiple)."""
    return max(multiple, round(float(val) / multiple) * multiple)


def calculate_dimensions_for_aspect_and_mp(aspect: str, megapixels: float) -> Tuple[int, int]:
    """Calculate width and height snapped to 32px grid for a given aspect ratio string and MP target."""
    aspect_map = {
        "1:1": (1, 1),
        "16:9": (16, 9),
        "9:16": (9, 16),
        "4:3": (4, 3),
        "3:4": (3, 4),
        "21:9": (21, 9),
        "2:1": (2, 1),
        "1:2": (1, 2),
        "3:2": (3, 2),
        "2:3": (2, 3),
    }
    ratio_w, ratio_h = aspect_map.get(aspect, (16, 9))
    target_pixels = megapixels * 1_000_000.0
    
    aspect_val = ratio_w / ratio_h
    raw_h = math.sqrt(target_pixels / aspect_val)
    raw_w = raw_h * aspect_val
    
    w = snap_to_multiple(raw_w, CANVAS_MULTIPLE)
    h = snap_to_multiple(raw_h, CANVAS_MULTIPLE)
    return w, h
