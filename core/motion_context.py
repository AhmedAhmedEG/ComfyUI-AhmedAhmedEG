"""Non-invasive runtime patches for MiniMax H3 PackedLayout & Payload to enable Motion Context."""

from __future__ import annotations

import inspect
import logging
from typing import Any, Dict, List, Optional, Tuple

import torch

log = logging.getLogger("MiniMaxH3MasterDirector.motion_context")

# Context markers
CTX_FRAME_KEY = "master_context_index"
CTX_AUDIO_END_KEY = "master_context_audio_end"
LAYOUT_PATCH_MARKER = "_master_director_layout_patch"
PAYLOAD_PATCH_MARKER = "_master_director_payload_patch"

_orig_layout_init = None
_layout_patched = False
_orig_extra_conds = None
_payload_patched = False

_REF_KINDS = ("ref_img", "ref_audio")


def _get_minimax_model_module():
    try:
        import comfy.ldm.minimax.model as mm
        return mm
    except Exception:
        return None


def _target_origin(layout) -> float:
    """Time coordinate where the target video segment begins."""
    a, b, kind = layout.segments[-1]
    if kind != "video" or b <= a:
        raise RuntimeError(
            f"Motion Context: expected final PackedLayout segment to be target video, got {kind!r}."
        )
    return float(layout.position_ids[a, 0])


def _keyframe_time_coord(mm, text_len: float, latent_t: int, frame_count: Optional[int], pixel_index: int) -> float:
    """Calculate time coordinate for a keyframe pixel index."""
    p = int(pixel_index)
    if p == 0:
        return float(text_len)
    if frame_count is not None and p == int(frame_count) - 1:
        return float(text_len) + sum(mm._video_t_spans(latent_t)) - mm.FRAME_RESCALE
    return float(text_len) + mm.FRAME_RESCALE * float(p)


def _expected_ref_kinds(block: dict) -> tuple[str, ...]:
    kind = block.get("kind")
    if kind == "image":
        return ("ref_img",)
    if kind == "audio":
        return ("ref_audio",) if int(block.get("ref_audio_t", 0) or 0) > 0 else ()
    if kind in ("video", "video_audio"):
        if int(block.get("ref_audio_t", 0) or 0) > 0:
            return ("ref_audio", "ref_img")
        return ("ref_img",)
    raise RuntimeError(f"Motion Context: unknown reference kind {kind!r}.")


def _ref_segments(layout, refs: list | None) -> dict[int, dict[str, tuple[int, int]]]:
    ref_segs = [(a, b, k) for a, b, k in layout.segments if k in _REF_KINDS]
    wanted = [(i, k) for i, blk in enumerate(refs or []) for k in _expected_ref_kinds(blk)]
    if len(wanted) != len(ref_segs):
        raise RuntimeError(
            f"Motion Context: reference segment count mismatch (expected {len(wanted)}, layout has {len(ref_segs)})."
        )
    out: dict[int, dict[str, tuple[int, int]]] = {}
    for (i, kind), (a, b, got) in zip(wanted, ref_segs):
        if got != kind:
            raise RuntimeError(f"Motion Context: reference block {i} expected {kind}, got {got}.")
        out.setdefault(i, {})[kind] = (a, b)
    return out


def _rewrite_keyframe_times(layout, text_len, latent_t, frame_count, keyframes):
    mm = _get_minimax_model_module()
    if mm is None:
        return
    offset = _target_origin(layout) - float(text_len)
    cond_spans = [(a, b) for a, b, kind in layout.segments if kind == "cond"]
    if len(cond_spans) != len(keyframes):
        return

    for (a, b), kf in zip(cond_spans, keyframes):
        p = kf.get(CTX_FRAME_KEY)
        if p is None:
            continue
        layout.position_ids[a:b, 0] = _keyframe_time_coord(mm, text_len, latent_t, frame_count, int(p)) + offset


def _rewrite_audio_timeline(layout, refs):
    mm = _get_minimax_model_module()
    if mm is None:
        return
    marked = [i for i, r in enumerate(refs or []) if r.get(CTX_AUDIO_END_KEY) is not None]
    if len(marked) != 1:
        return

    idx = marked[0]
    blk = refs[idx]
    if blk.get("kind") != "audio":
        return

    rt = int(blk.get("ref_audio_t", 0) or 0)
    if rt <= 0:
        return

    seg = _ref_segments(layout, refs).get(idx, {}).get("ref_audio")
    if seg is None:
        return

    a, b = seg
    origin = _target_origin(layout)
    slot_start = float(layout.position_ids[a, 0])
    end_frame = float(blk[CTX_AUDIO_END_KEY])
    desired_start = origin + mm.FRAME_RESCALE * end_frame - float(rt)
    layout.position_ids[a:b, 0] = layout.position_ids[a:b, 0] + (desired_start - slot_start)


def _director_layout_init(
    self,
    text_len,
    latent_t,
    latent_h,
    latent_w,
    audio_t,
    keyframes=None,
    refs=None,
    frame_count=None,
):
    # Stock accepts only first/last (index 0 or last); pass interior anchors as index 0, then rewrite
    stock_keyframes = None
    if keyframes:
        stock_keyframes = []
        for kf in keyframes:
            entry = dict(kf)
            if CTX_FRAME_KEY in entry:
                entry["resolved_frame_index"] = 0
            stock_keyframes.append(entry)

    # Call original layout init
    orig = _orig_layout_init
    if orig is not None:
        try:
            orig(self, text_len, latent_t, latent_h, latent_w, audio_t, keyframes=stock_keyframes, refs=refs, frame_count=frame_count)
        except TypeError:
            orig(self, text_len, latent_t, latent_h, latent_w, audio_t, keyframes=stock_keyframes, refs=refs)

    has_ctx_kf = bool(keyframes) and any(kf.get(CTX_FRAME_KEY) is not None for kf in keyframes)
    has_ctx_audio = bool(refs) and any(r.get(CTX_AUDIO_END_KEY) is not None for r in refs)

    if has_ctx_kf:
        _rewrite_keyframe_times(self, text_len, latent_t, frame_count, keyframes)
    if has_ctx_audio:
        _rewrite_audio_timeline(self, refs)


setattr(_director_layout_init, LAYOUT_PATCH_MARKER, True)


def patch_packed_layout_init():
    """Install PackedLayout patch to handle interior keyframes and motion context offsets."""
    global _orig_layout_init, _layout_patched
    if _layout_patched:
        return

    mm = _get_minimax_model_module()
    if mm is None or not hasattr(mm, "PackedLayout"):
        return

    init = getattr(mm.PackedLayout, "__init__", None)
    if init is None or getattr(init, LAYOUT_PATCH_MARKER, False):
        _layout_patched = True
        return

    _orig_layout_init = init
    mm.PackedLayout.__init__ = _director_layout_init
    _layout_patched = True
    log.info("Installed PackedLayout Motion Context runtime patch.")


def _director_extra_conds(self, **kwargs):
    out = _orig_extra_conds(self, **kwargs) if _orig_extra_conds else {}
    keyframes = kwargs.get("minimax_keyframes")
    refs = kwargs.get("minimax_refs")
    if not keyframes or not refs:
        return out

    if not (
        any(CTX_FRAME_KEY in kf for kf in keyframes)
        or any(CTX_AUDIO_END_KEY in r for r in refs)
    ):
        return out

    cond = out.get("minimax_payload")
    payload = getattr(cond, "cond", None) if cond is not None else None
    if not isinstance(payload, dict):
        return out

    kf_video = [kf["latent"] for kf in keyframes if "latent" in kf]
    ref_video = [r["latent"] for r in refs if "latent" in r]
    payload["cond_video_latents"] = kf_video + ref_video
    payload["cond_audio_latents"] = [
        r["audio_latent"] for r in refs if r.get("audio_latent") is not None
    ]
    fc = kwargs.get("minimax_frame_count")
    if fc is not None:
        payload["frame_count"] = fc
    return out


setattr(_director_extra_conds, PAYLOAD_PATCH_MARKER, True)


def patch_model_extra_conds():
    """Install payload merge patch to ensure keyframes and references coexist."""
    global _orig_extra_conds, _payload_patched
    if _payload_patched:
        return

    try:
        import comfy.model_base as model_base
        cls = getattr(model_base, "MiniMaxH3", None)
        if cls is None or not hasattr(cls, "extra_conds"):
            return

        fn = getattr(cls, "extra_conds", None)
        if fn is None or getattr(fn, PAYLOAD_PATCH_MARKER, False):
            _payload_patched = True
            return

        _orig_extra_conds = fn
        cls.extra_conds = _director_extra_conds
        _payload_patched = True
        log.info("Installed MiniMaxH3.extra_conds coexistence runtime patch.")
    except Exception as exc:
        log.debug(f"Could not patch extra_conds: {exc}")


def ensure_motion_context_patches():
    """Ensure both runtime patches are active."""
    patch_packed_layout_init()
    patch_model_extra_conds()
