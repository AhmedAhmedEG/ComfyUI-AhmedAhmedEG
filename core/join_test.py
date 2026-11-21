"""Fast join test: sample only the opening of a continuing clip.

The Master editor's "Test join" button runs one clip in this mode. Everything
is prepared exactly as for the full clip (references, continuity context,
conditioning, seed), then the latent is cut to the reused context plus about a
second of new frames just before sampling. The sampling noise is generated for
the full-length latent and cut the same way, so the opening frames start from
the very noise the full clip would use. Only the measured look of the opening
is kept (``join_tests.json`` in the project folder); no take is saved.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
import time

JOIN_TEST_FRAMES = 33       # new pixel frames after the reused context (~1.4 s)
LATENT_STRIDE = 8           # H3 video latent frames per pixel frame step
RESULTS_FILE = "join_tests.json"


def keep_video_tokens(context_frames, new_frames=JOIN_TEST_FRAMES):
    """Video latent frames covering ``context_frames + new_frames`` pixel frames."""
    frames = max(1, int(context_frames) + int(new_frames))
    return 1 + math.ceil((frames - 1) / LATENT_STRIDE)


def _streams(value):
    return list(value.unbind()) if getattr(value, "is_nested", False) else [value]


def _pack(streams, like):
    if getattr(like, "is_nested", False):
        import comfy.nested_tensor
        return comfy.nested_tensor.NestedTensor(streams)
    return streams[0]


def _cut_video(t, keep):
    if t.ndim >= 5 and t.shape[2] > keep:
        return t[:, :, :keep]
    if t.ndim == 3 and t.shape[-1] > keep:
        return t[..., :keep]
    return t


def _cut_audio(t, keep):
    return t[..., :keep] if t.shape[-1] > keep else t


def cut_for_join_test(latent, seed, context_frames, new_frames=JOIN_TEST_FRAMES):
    """Return ``(short_latent, noise)``: the opening of ``latent`` and its full-length noise, cut."""
    import comfy.sample
    samples = latent["samples"]
    noise = comfy.sample.prepare_noise(samples, seed, latent.get("batch_index"))
    s, n = _streams(samples), _streams(noise)
    full_t = int(s[0].shape[2])
    keep_v = min(full_t, keep_video_tokens(context_frames, new_frames))
    keep_a = None
    if len(s) > 1:
        full_a = int(s[1].shape[-1])
        keep_a = max(1, min(full_a, math.ceil(full_a * keep_v / max(1, full_t))))

    def cut(streams):
        out = [_cut_video(streams[0], keep_v)]
        if len(streams) > 1:
            out.append(_cut_audio(streams[1], keep_a))
        out.extend(streams[2:])
        return out

    short = dict(latent)
    short["samples"] = _pack(cut(s), samples)
    mask = latent.get("noise_mask")
    if mask is not None:
        m = _streams(mask)
        short["noise_mask"] = _pack(cut(m), mask) if len(m) == len(s) else mask
    return short, _pack(cut(n), noise), keep_v, full_t


def save_result(project_dir, clip_id, result):
    """Store the newest join test of ``clip_id`` (atomic write, one entry per clip)."""
    path = os.path.join(project_dir, RESULTS_FILE)
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    data[str(clip_id)] = {**result, "time": time.time()}
    fd, tmp = tempfile.mkstemp(dir=project_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(data, out)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def load_result(project_dir, clip_id):
    try:
        with open(os.path.join(project_dir, RESULTS_FILE), encoding="utf-8") as handle:
            data = json.load(handle)
        row = data.get(str(clip_id)) if isinstance(data, dict) else None
        return row if isinstance(row, dict) else None
    except (OSError, ValueError):
        return None
