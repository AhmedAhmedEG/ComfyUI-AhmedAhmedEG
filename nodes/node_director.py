"""Primary custom node: MiniMax H3 Master Director."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import torch
import torch.nn.functional as F

try:
    from ..core.config import (
        FPS,
        CANVAS_MULTIPLE,
        align_frame_count,
        calculate_dimensions_for_aspect_and_mp,
    )
    from ..core.task_modes import (
        SUPPORTED_MODES,
        MODE_FL2VA,
        MODE_REF2VA,
        MODE_INPAINT,
        normalize_mode,
        get_required_model_type,
    )
    from ..core.media_io import load_image, load_video, load_audio, load_embedded_video_audio
    from ..core.refmod import process_refmod_rows, build_refmod_tag_map, translate_refmod_aliases
    from ..core.prompt_engine import build_keyframe_mode_prompt, build_ref2va_prompt
    from ..core.continuity import (
        slice_continuity_tail,
        trim_continuity_prefix,
        trim_continuity_audio_prefix,
        match_color_temperature_and_grade,
        repack_av_latent,
        extract_streams_from_av_latent,
        unpack_av_samples,
    )
    from ..core.executor import (
        MasterDirectorExecutor,
        decode_video_latent,
        decode_audio_latent,
    )
    from ..core.selflift import sample_selflift_progressive
    from ..core.refine import apply_refine_pass
    from ..core.face_refine import apply_face_refinement
    from ..core.audio_post import concatenate_audio_clips
    from ..core.cache_manager import ProjectCacheManager, compute_clip_fingerprint
except (ImportError, ValueError):
    from core.config import (
        FPS,
        CANVAS_MULTIPLE,
        align_frame_count,
        calculate_dimensions_for_aspect_and_mp,
    )
    from core.task_modes import (
        SUPPORTED_MODES,
        MODE_FL2VA,
        MODE_REF2VA,
        MODE_INPAINT,
        normalize_mode,
        get_required_model_type,
    )
    from core.media_io import load_image, load_video, load_audio, load_embedded_video_audio
    from core.refmod import process_refmod_rows, build_refmod_tag_map, translate_refmod_aliases
    from core.prompt_engine import build_keyframe_mode_prompt, build_ref2va_prompt
    from core.continuity import (
        slice_continuity_tail,
        trim_continuity_prefix,
        trim_continuity_audio_prefix,
        match_color_temperature_and_grade,
        repack_av_latent,
        extract_streams_from_av_latent,
        unpack_av_samples,
    )
    from core.executor import (
        MasterDirectorExecutor,
        decode_video_latent,
        decode_audio_latent,
    )
    from core.selflift import sample_selflift_progressive
    from core.refine import apply_refine_pass
    from core.face_refine import apply_face_refinement
    from core.audio_post import concatenate_audio_clips
    from core.cache_manager import ProjectCacheManager, compute_clip_fingerprint

log = logging.getLogger("MiniMaxH3MasterDirector.node")

CATEGORY = "ComfyUI-AhmedAhmedEG"


class MiniMaxH3MasterDirector:
    """Unified master director node combining multi-track authoring, prompt engineering, and AV generation."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_vae": ("VAE", {"tooltip": "MiniMax H3 Video VAE (minimax_h3_video_vae)."}),
                "audio_vae": ("VAE", {"tooltip": "MiniMax H3 Audio VAE (minimax_h3_audio_vae). Required for REF2VA & Audio."}),
                "clip": ("CLIP", {"tooltip": "MiniMax H3 Qwen3-VL CLIP model."}),
            },
            "optional": {
                "model": ("MODEL", {"lazy": True, "tooltip": "General MiniMax H3 diffusion model (or use fl2va_model / ref2va_model sockets)."}),
                "config": ("MMX_DIRECTOR_CONFIG", {"tooltip": "Sampling, canvas, and pipeline settings (MiniMaxH3DirectorSettings)."}),
                "ref_pack": ("MMX_REF_PACK", {"tooltip": "Reference pool containing images, videos, and audios (MiniMaxH3RefPack)."}),
                "fl2va_model": ("MODEL", {"lazy": True, "tooltip": "Lazy-loaded FL2VA UNET."}),
                "ref2va_model": ("MODEL", {"lazy": True, "tooltip": "Lazy-loaded REF2VA UNET."}),
                "selflift": ("MMX_DIR_SELFLIFT", {"tooltip": "Optional SelfLift progressive sampling settings."}),
                "refine": ("MMX_DIR_REFINE", {"tooltip": "Optional 2nd-pass refine and upscale settings."}),
                "face_refine": ("MMX_DIR_FACE_REFINE", {"tooltip": "Optional FaceRefine close-up tracking & stitch."}),
                "semantic_bridge": ("MMX_DIR_SEMANTIC_BRIDGE", {"tooltip": "Optional Semantic Bridge student MLP conditioning rewrite."}),
                "i2v_groups": ("MMX_DIR_GROUP", {"tooltip": "Optional external Image to Video groups."}),
                "r2v_groups": ("MMX_DIR_GROUP", {"tooltip": "Optional external Reference to Video groups."}),
                "sigmas": ("SIGMAS", {"forceInput": True, "tooltip": "External sigma schedule override."}),
                "prompt_pack": ("PROMPT_PACK", {"tooltip": "External prompt pack bridge."}),
                "timeline_data": ("STRING", {"default": "{\"version\":1,\"clips\":[]}", "multiline": False}),
                "builder_state": ("STRING", {"default": "{}", "multiline": False}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            },
        }

    RETURN_TYPES = ("IMAGE", "AUDIO", "VHS_VIDEOINFO", "CONDITIONING", "LATENT", "STRING", "FLOAT", "INT", "STRING")
    RETURN_NAMES = ("images", "audio", "video", "positive", "latent", "resolved_prompt", "fps", "frame_count", "status")
    FUNCTION = "execute"
    CATEGORY = CATEGORY

    @classmethod
    def check_lazy_status(
        cls,
        model=None,
        fl2va_model=None,
        ref2va_model=None,
        timeline_data="{}",
        **kwargs,
    ):
        """Determine which model inputs need evaluation based on active timeline clip modes."""
        if model is not None:
            return []

        try:
            tl = json.loads(timeline_data or "{}") if isinstance(timeline_data, str) else timeline_data
            clips = tl.get("clips", []) if isinstance(tl, dict) else []
            if clips:
                types = {c.get("type", "T2V").upper() for c in clips}
            else:
                types = set()
        except Exception:
            types = set()

        if not types:
            return ["model"] if model is None else []

        needs_fl2va = any(t in ("FL2VA", "FL2V", "I2VA", "I2V", "L2VA", "T2VA", "T2V", "IMAGE INPAINT") for t in types)
        needs_ref2va = any(t in ("REF2VA", "REF2V", "V2V") for t in types)

        needed = []
        if needs_fl2va and fl2va_model is None:
            needed.append("fl2va_model")
        if needs_ref2va and ref2va_model is None:
            needed.append("ref2va_model")

        return needed

    def execute(
        self,
        model=None,
        video_vae=None,
        audio_vae=None,
        clip=None,
        config=None,
        ref_pack=None,
        fl2va_model=None,
        ref2va_model=None,
        selflift=None,
        refine=None,
        face_refine=None,
        semantic_bridge=None,
        i2v_groups=None,
        r2v_groups=None,
        sigmas=None,
        prompt_pack=None,
        timeline_data="{}",
        builder_state="{}",
        unique_id="default_director",
        **kwargs,
    ):
        # Extract execution mode first to determine if diffusion models are required
        cfg_dict = config if config and isinstance(config, dict) else {}
        exec_mode = str(
            kwargs.get("execution_mode")
            or cfg_dict.get("execution_mode")
            or "Full Generation"
        )
        if exec_mode != "Conditioning Guide Output" and model is None and fl2va_model is None and ref2va_model is None:
            raise ValueError(
                "MiniMaxH3MasterDirector requires at least one diffusion model input. "
                "Please connect 'model', 'fl2va_model', or 'ref2va_model'."
            )

        # Extract settings from config with sensible defaults or legacy kwargs
        cfg_dict = config if config and isinstance(config, dict) else {}
        width = int(kwargs.get("width", cfg_dict.get("width", 1344)))
        height = int(kwargs.get("height", cfg_dict.get("height", 768)))
        duration = float(kwargs.get("duration", cfg_dict.get("duration", 5.0)))
        frame_rate = float(kwargs.get("frame_rate", cfg_dict.get("frame_rate", 24.0)))
        steps = int(kwargs.get("steps", cfg_dict.get("steps", 25)))
        cfg = float(kwargs.get("cfg", cfg_dict.get("cfg", 1.0)))
        sampler = str(kwargs.get("sampler", cfg_dict.get("sampler", "res_multistep")))
        scheduler = str(kwargs.get("scheduler", cfg_dict.get("scheduler", "simple")))
        shift_video = float(kwargs.get("shift_video", cfg_dict.get("shift_video", 12.0)))
        shift_audio = float(kwargs.get("shift_audio", cfg_dict.get("shift_audio", 3.0)))
        seed = int(kwargs.get("seed", cfg_dict.get("seed", 0)))
        execution_mode = str(kwargs.get("execution_mode", cfg_dict.get("execution_mode", "All-in-One Generation")))
        prompt_mode = str(kwargs.get("prompt_mode", cfg_dict.get("prompt_mode", "structured")))
        run_mode = str(kwargs.get("run_mode", cfg_dict.get("run_mode", "clip_by_clip")))
        continuity_mode = str(kwargs.get("continuity_mode", cfg_dict.get("continuity_mode", "Motion Context (Chained)")))
        context_length = str(kwargs.get("context_length", cfg_dict.get("context_length", "22")))
        prompt = str(kwargs.get("prompt", cfg_dict.get("prompt", "")))
        mode = kwargs.get("mode", cfg_dict.get("mode", None))
        try:
            timeline = json.loads(timeline_data or "{}") if isinstance(timeline_data, str) else timeline_data
            if not isinstance(timeline, dict):
                timeline = {}
        except Exception:
            timeline = {}

        try:
            builder = json.loads(builder_state or "{}") if isinstance(builder_state, str) else builder_state
            if not isinstance(builder, dict):
                builder = {}
        except Exception:
            builder = {}

        executor = MasterDirectorExecutor(project_id=str(unique_id))

        # Check for RefMods from timeline or ref_pack
        refmod_rows = timeline.get("refmods", [])
        if not refmod_rows and ref_pack is not None and isinstance(ref_pack, dict):
            slot_counter = 1
            for r in ref_pack.get("refs", []):
                if isinstance(r, dict) and r.get("type") == "refmod":
                    mod_data = r.get("data")
                    if mod_data and str(mod_data).strip().lower() != "none":
                        refmod_rows.append({
                            "slot": slot_counter,
                            "name": str(mod_data).strip(),
                            "description": r.get("name", f"RefMod {slot_counter}"),
                            "strength": 1.0,
                            "enabled": True,
                        })
                        slot_counter += 1

        refmod_items = process_refmod_rows(refmod_rows) if refmod_rows else []
        # If files were not loaded from disk (e.g. mock or missing file), preserve metadata for tag translation
        if not refmod_items and refmod_rows:
            for r in refmod_rows:
                refmod_items.append({
                    "id": f"mod_{r['slot']}",
                    "slot": r["slot"],
                    "name": r.get("description", r["name"]),
                    "path": r["name"],
                    "kind": "image",
                    "scale": r.get("strength", 1.0),
                })

        # Build reference pool from ref_pack input
        ref_pool: Dict[str, Dict[str, Any]] = {}
        if ref_pack is not None and isinstance(ref_pack, dict):
            # Format 1: MiniMaxH3RefPack dict with "refs" list
            if "refs" in ref_pack and isinstance(ref_pack["refs"], list):
                for r in ref_pack["refs"]:
                    if isinstance(r, dict):
                        if "id" in r:
                            ref_pool[r["id"]] = r
                        if "slot_id" in r and (r.get("pack_index", 1) == 1 or r["slot_id"] not in ref_pool):
                            ref_pool[r["slot_id"]] = r
                        if "ref_id" in r:
                            ref_pool[r["ref_id"]] = r
            # Format 2: Bridge dict {"ref_image_1": ...}
            for k, v in ref_pack.items():
                if k not in ("refs", "pack_count", "version") and v is not None:
                    ref_pool[k] = {"id": k, "slot_id": k, "name": k, "type": "image", "data": v}

        # Parse clips from timeline
        clips = timeline.get("clips", [])
        if not clips:
            # Fallback single clip if timeline has no clips
            default_type = mode if mode else ("REF2VA" if ref_pool else "T2V")
            clips = [{
                "id": "clip_1",
                "name": "Shot 1",
                "type": default_type,
                "duration": duration,
                "prompt": prompt,
                "ref_ids": list(ref_pool.keys()),
                "continuity": True,
            }]

        project_id = str(cfg_dict.get("project_id", "default_master_director"))
        cache_mgr = ProjectCacheManager(project_id=project_id)
        preview_mode = str(
            kwargs.get("preview_mode")
            or timeline.get("preview_mode")
            or cfg_dict.get("preview_mode")
            or "full"
        ).lower()

        all_decoded_frames: List[torch.Tensor] = []
        all_decoded_audios: List[Dict[str, Any]] = []
        clip_chained_flags: List[bool] = [False] * len(clips)
        previous_tail: Optional[Dict[str, Any]] = None
        last_positive = None
        last_latent = None
        last_prompt = ""

        for clip_idx, clip_item in enumerate(clips):
            clip_id = str(clip_item.get("id") or f"clip_{clip_idx + 1}")
            clip_type = str(clip_item.get("type", "T2V")).upper()
            clip_dur = float(clip_item.get("duration", duration))
            clip_prompt_text = str(clip_item.get("prompt", "") or prompt or "")
            clip_continuity = bool(clip_item.get("continuity", True))
            clip_ref_ids = clip_item.get("ref_ids", [])
            if "tail_seconds" in clip_item:
                clip_tail_sec = float(clip_item["tail_seconds"])
            elif "tail_frames" in clip_item:
                clip_tail_sec = float(clip_item["tail_frames"]) / frame_rate
            else:
                clip_tail_sec = 0.5
            if clip_tail_sec <= 0.0:
                clip_continuity = False
            clip_validated = bool(clip_item.get("validated", False))

            if clip_item.get("seed") is not None and str(clip_item.get("seed")).isdigit():
                clip_seed = int(clip_item["seed"]) & 0xFFFFFFFFFFFFFFFF
            else:
                clip_seed = (seed + clip_idx * 1000) & 0xFFFFFFFFFFFFFFFF

            # Map clip_type to canonical MiniMax mode (unifying REF2V into REF2VA)
            if clip_type in ("T2V", "TEXT"):
                canon_mode = "FL2VA"
            elif clip_type in ("I2V", "IMAGE"):
                canon_mode = "I2VA"
            elif clip_type in ("FL2V", "FIRST_LAST"):
                canon_mode = "FL2VA"
            elif clip_type in ("V2V", "VIDEO"):
                canon_mode = "V2V"
            else:
                canon_mode = "REF2VA"

            # Select model for this clip
            clip_active_model = fl2va_model if canon_mode in ("FL2VA", "I2VA", "L2VA", "T2VA", "Image Inpaint") and fl2va_model is not None else (
                ref2va_model if ref2va_model is not None else model
            )
            if execution_mode != "Conditioning Guide Output" and clip_active_model is None:
                needed_type = "fl2va_model" if canon_mode in ("FL2VA", "I2VA", "L2VA", "T2VA") else "ref2va_model"
                raise ValueError(
                    f"MiniMaxH3MasterDirector: Shot {clip_idx + 1} ({clip_type} -> {canon_mode}) requires a model, "
                    f"but neither '{needed_type}' nor 'model' was connected."
                )

            # Resolve local references assigned to this clip
            local_imgs = []
            local_vids = []
            local_auds = []
            for rid in clip_ref_ids:
                robj = ref_pool.get(rid)
                if not robj:
                    continue
                rtype = robj.get("type")
                rdata = robj.get("data")
                if rdata is None:
                    continue
                if rtype == "image":
                    local_imgs.append(rdata)
                elif rtype == "video":
                    local_vids.append(rdata)
                elif rtype == "audio":
                    local_auds.append(rdata)

            first_frame = None
            last_frame = None
            ref_images = {}
            ref_videos = {}
            ref_audios = {}

            # Automatic internal continuity: inject previous clip's tail frame
            is_chained_from_previous = False
            if clip_continuity and previous_tail is not None and clip_idx > 0:
                first_frame = previous_tail["last_frame"]
                is_chained_from_previous = True

            if clip_type in ("I2V", "IMAGE"):
                if local_imgs:
                    first_frame = local_imgs[0]
                    is_chained_from_previous = False
            elif clip_type in ("FL2V", "FIRST_LAST"):
                if len(local_imgs) >= 2:
                    first_frame = local_imgs[0]
                    last_frame = local_imgs[1]
                    is_chained_from_previous = False
                elif len(local_imgs) == 1:
                    if first_frame is not None:
                        last_frame = local_imgs[0]
                    else:
                        first_frame = local_imgs[0]
                        is_chained_from_previous = False
            elif clip_type in ("V2V", "VIDEO"):
                for i, v in enumerate(local_vids):
                    ref_videos[f"ref_video_{i+1}"] = v
                is_chained_from_previous = False
            else: # REF2VA
                for i, img in enumerate(local_imgs):
                    ref_images[f"ref_image_{i+1}"] = img
                for i, v in enumerate(local_vids):
                    ref_videos[f"ref_video_{i+1}"] = v
                for i, a in enumerate(local_auds):
                    ref_audios[f"ref_audio_{i+1}"] = a

                # Automatic internal continuity for REF2VA: if no local visual references were assigned, inject tail
                if clip_continuity and previous_tail is not None and clip_idx > 0:
                    if not ref_images and not ref_videos and previous_tail.get("last_frame") is not None:
                        ref_images["ref_image_1"] = previous_tail["last_frame"]
                    if not ref_audios and previous_tail.get("tail_audio") is not None:
                        ref_audios["ref_audio_1"] = previous_tail["tail_audio"]
                is_chained_from_previous = False

            clip_chained_flags[clip_idx] = is_chained_from_previous

            # Build prompt (supporting per-clip structured prompts or raw prompts)
            tag_map = build_refmod_tag_map(refmod_items, len(ref_images), len(ref_videos), len(ref_audios))
            clip_prompt_mode = clip_item.get("prompt_mode", prompt_mode)
            clip_structured = clip_item.get("structured_prompt")

            if clip_prompt_mode == "structured" and isinstance(clip_structured, dict) and any(str(v).strip() for v in clip_structured.values()):
                c_soundscape = clip_structured.get("overall_soundscape") or clip_structured.get("soundscape", "")
                c_music = clip_structured.get("non_diegetic_music") or clip_structured.get("music", "")
                if canon_mode == "REF2VA":
                    resolved_prompt = build_ref2va_prompt(
                        subject_definitions=translate_refmod_aliases(clip_structured.get("subject_definitions", ""), tag_map),
                        summary=translate_refmod_aliases(clip_structured.get("summary", ""), tag_map),
                        retention_analysis=translate_refmod_aliases(clip_structured.get("retention_analysis", ""), tag_map),
                        detailed_description=translate_refmod_aliases(clip_structured.get("detailed_description", ""), tag_map),
                        soundscape=translate_refmod_aliases(c_soundscape, tag_map),
                        music=translate_refmod_aliases(c_music, tag_map),
                        prompt_mode="structured",
                    )
                else:
                    resolved_prompt = build_keyframe_mode_prompt(
                        mode=canon_mode,
                        imd=clip_structured.get("imd", clip_structured.get("detailed_description", "")),
                        soundscape=c_soundscape,
                        music=c_music,
                        duration_sec=clip_dur,
                        has_first_frame=first_frame is not None,
                        has_last_frame=last_frame is not None,
                        prompt_mode="structured",
                    )
            elif clip_prompt_text:
                resolved_prompt = translate_refmod_aliases(clip_prompt_text, tag_map)
            elif canon_mode == "REF2VA":
                ref_dict = builder.get("ref", {})
                b_soundscape = ref_dict.get("overall_soundscape") or ref_dict.get("soundscape", "")
                b_music = ref_dict.get("non_diegetic_music") or ref_dict.get("music", "")
                resolved_prompt = build_ref2va_prompt(
                    subject_definitions=translate_refmod_aliases(ref_dict.get("subject_definitions", ""), tag_map),
                    summary=translate_refmod_aliases(ref_dict.get("summary", ""), tag_map),
                    retention_analysis=translate_refmod_aliases(ref_dict.get("retention_analysis", ""), tag_map),
                    detailed_description=translate_refmod_aliases(ref_dict.get("detailed_description", ""), tag_map),
                    soundscape=translate_refmod_aliases(b_soundscape, tag_map),
                    music=translate_refmod_aliases(b_music, tag_map),
                    prompt_mode=prompt_mode,
                )
            else:
                b_soundscape = builder.get("overall_soundscape") or builder.get("soundscape", "")
                b_music = builder.get("non_diegetic_music") or builder.get("music", "")
                resolved_prompt = build_keyframe_mode_prompt(
                    mode=canon_mode,
                    imd=builder.get("imd", ""),
                    soundscape=b_soundscape,
                    music=b_music,
                    duration_sec=clip_dur,
                    has_first_frame=first_frame is not None,
                    has_last_frame=last_frame is not None,
                    prompt_mode=prompt_mode,
                )

            # Generate conditioning for this clip
            positive, latent, final_prompt = executor.build_conditioning(
                mode=canon_mode,
                prompt=resolved_prompt,
                width=width,
                height=height,
                duration=clip_dur,
                clip=clip,
                vae=video_vae,
                audio_vae=audio_vae,
                first_frame=first_frame,
                last_frame=last_frame,
                ref_images=ref_images,
                ref_videos=ref_videos,
                ref_audios=ref_audios,
                refmod_items=refmod_items,
            )

            # Apply Semantic Bridge if wired
            if semantic_bridge is not None:
                try:
                    from .node_semantic_bridge import apply_semantic_bridge
                    positive = apply_semantic_bridge(positive, semantic_bridge, task_key=canon_mode)
                except Exception as exc:
                    log.warning(f"Semantic Bridge rewrite skipped: {exc}")

            last_positive = positive
            last_latent = latent
            last_prompt = final_prompt

            if execution_mode == "Conditioning Guide Output":
                continue

            # Fingerprint calculation for caching and validation
            clip_fp = compute_clip_fingerprint(
                prompt=final_prompt,
                duration=clip_dur,
                width=width,
                height=height,
                seed=clip_seed,
                model_name=getattr(clip_active_model, "model_name", "h3"),
                loras=clip_item.get("loras"),
            )

            # If clip is validated and stored in server cache, skip diffusion sampling!
            if clip_validated and cache_mgr.is_clip_cached_and_valid(clip_id, clip_fp):
                cached_frames = cache_mgr.load_clip_frames(clip_id)
                cached_audio = cache_mgr.load_clip_audio(clip_id)
                cached_latent = cache_mgr.load_clip_latent(clip_id)
                if cached_frames is not None:
                    log.info(f"Master Director: Clip {clip_idx + 1}/{len(clips)} [{clip_id}] is validated & cached. Skipping diffusion sampling.")
                    all_decoded_frames.append(cached_frames)
                    all_decoded_audios.append(
                        cached_audio if cached_audio is not None else {"waveform": torch.zeros((1, 2, 48000)), "sample_rate": 48000}
                    )
                    v_stream, _ = extract_streams_from_av_latent(cached_latent) if cached_latent else (None, None)
                    tail_count = max(1, min(int(cached_frames.shape[0]), int(round(clip_tail_sec * frame_rate))))
                    cached_aud = cached_audio if cached_audio is not None else {"waveform": torch.zeros((1, 2, 48000)), "sample_rate": 48000}
                    wf_c = cached_aud["waveform"]
                    sr_c = int(cached_aud.get("sample_rate", 48000))
                    aud_samples_c = min(wf_c.shape[-1], max(1, int(round(clip_tail_sec * sr_c))))
                    cached_tail_aud = {"waveform": wf_c[..., -aud_samples_c:].clone(), "sample_rate": sr_c}
                    previous_tail = {
                        "last_frame": cached_frames[-1:].clone(),
                        "tail_frames": cached_frames[-tail_count:].clone(),
                        "tail_latent": v_stream[:, :, -1:].clone() if hasattr(v_stream, "shape") and getattr(v_stream, "ndim", 0) >= 3 else None,
                        "tail_audio": cached_tail_aud,
                    }
                    continue

            # Sampling
            import comfy.sample
            import comfy.samplers

            try:
                from comfy_extras.nodes_minimax_h3 import MiniMaxH3SigmaShift
                shifted = MiniMaxH3SigmaShift.execute(clip_active_model, float(shift_video), float(shift_audio))
                shifted_model = shifted[0] if isinstance(shifted, (tuple, list)) else shifted
            except Exception:
                shifted_model = clip_active_model.clone() if hasattr(clip_active_model, "clone") else clip_active_model
                shifted_model.model_options = dict(getattr(shifted_model, "model_options", None) or {})
                shifted_model.model_options["minimax_h3_sigma_shift_video"] = float(shift_video)
                shifted_model.model_options["minimax_h3_sigma_shift_audio"] = float(shift_audio)
                tr_opts = dict(shifted_model.model_options.get("transformer_options", {}))
                tr_opts["minimax_h3_sigma_shift_video"] = float(shift_video)
                tr_opts["minimax_h3_sigma_shift_audio"] = float(shift_audio)
                shifted_model.model_options["transformer_options"] = tr_opts

            negative = []
            clip_frames_count = align_frame_count(int(clip_dur * frame_rate))
            log.info(f"Master Director: Sampling clip {clip_idx + 1}/{len(clips)} [{clip_type} -> {canon_mode}] ({clip_frames_count} frames, seed={clip_seed})...")

            if selflift is not None and selflift.get("enabled", False):
                sampled_latent = sample_selflift_progressive(
                    model=shifted_model,
                    positive=positive,
                    negative=negative,
                    latent_dict=latent,
                    seed=clip_seed,
                    total_steps=steps,
                    cfg=cfg,
                    lowres_scale=selflift.get("lowres_scale", 0.5),
                    highres_steps=selflift.get("highres_steps", 4),
                )
            else:
                sampled_latent = comfy.sample.sample(
                    shifted_model,
                    latent,
                    steps,
                    cfg,
                    sampler,
                    scheduler,
                    positive,
                    negative,
                    clip_seed,
                    denoise=1.0,
                )

            # Optional second-pass Refine
            if refine is not None and refine.get("enabled", False):
                sampled_latent = apply_refine_pass(
                    model=clip_active_model,
                    latent_dict=sampled_latent,
                    positive=positive,
                    negative=negative,
                    seed=clip_seed,
                    refine_mode=refine.get("mode", "refine"),
                    target_width=refine.get("target_width", width),
                    target_height=refine.get("target_height", height),
                    steps=refine.get("steps", 3),
                    denoise=refine.get("denoise", 0.45),
                    enable_tiling=refine.get("enable_tiling", False),
                    tile_count=refine.get("tile_count", 2),
                    tile_overlap=refine.get("tile_overlap", 128),
                )

            # Decode
            v_stream, a_stream = extract_streams_from_av_latent(sampled_latent)
            decoded_frames = decode_video_latent(video_vae, v_stream)
            decoded_audio = decode_audio_latent(audio_vae, a_stream) if audio_vae else {"waveform": torch.zeros((1, 2, 48000)), "sample_rate": 48000}

            # Continuity Seam Color Grading
            if clip_idx > 0 and clip_continuity and previous_tail is not None and "tail_frames" in previous_tail:
                try:
                    blend_w = min(12, int(decoded_frames.shape[0]))
                    decoded_frames = match_color_temperature_and_grade(
                        decoded_frames,
                        previous_tail["tail_frames"],
                        blend_window=blend_w,
                    )
                except Exception as cg_err:
                    log.warning(f"Master Director: Seam color grading failed for clip {clip_idx}: {cg_err}")

            # Optional FaceRefine
            if face_refine is not None and face_refine.get("enabled", False):
                decoded_frames, _ = apply_face_refinement(
                    decoded_frames=decoded_frames,
                    model=clip_active_model,
                    vae=video_vae,
                    clip=clip,
                    seed=clip_seed,
                    prompt=face_refine.get("prompt", "cinematic sharp portrait face"),
                    strength=face_refine.get("strength", 0.35),
                    crop_size=face_refine.get("crop_size", 512),
                    detector_name=face_refine.get("detector", "face_yolov8m.pt"),
                )

            all_decoded_frames.append(decoded_frames)
            all_decoded_audios.append(decoded_audio)

            # Store result in cache manager
            try:
                cache_mgr.store_clip_results(
                    clip_id=clip_id,
                    fingerprint=clip_fp,
                    latent_dict=sampled_latent,
                    audio_dict=decoded_audio,
                    decoded_frames=decoded_frames,
                    validated=clip_validated,
                )
            except Exception as c_err:
                log.warning(f"Master Director: Could not cache clip {clip_id}: {c_err}")

            # Extract tail for subsequent clip continuity using per-clip tail_seconds
            tail_count = max(1, min(int(decoded_frames.shape[0]), int(round(clip_tail_sec * frame_rate))))
            wf_d = decoded_audio["waveform"]
            sr_d = int(decoded_audio.get("sample_rate", 48000))
            aud_samples_d = min(wf_d.shape[-1], max(1, int(round(clip_tail_sec * sr_d))))
            tail_aud = {"waveform": wf_d[..., -aud_samples_d:].clone(), "sample_rate": sr_d}
            previous_tail = {
                "last_frame": decoded_frames[-1:].clone(),
                "tail_frames": decoded_frames[-tail_count:].clone(),
                "tail_latent": v_stream[:, :, -1:].clone() if hasattr(v_stream, "shape") and getattr(v_stream, "ndim", 0) >= 3 else None,
                "tail_audio": tail_aud,
            }

        # Handle outputs
        if execution_mode == "Conditioning Guide Output":
            total_dur = sum(float(c.get("duration", duration)) for c in clips)
            total_frames = align_frame_count(int(total_dur * frame_rate))
            dummy_img = torch.zeros((1, height, width, 3), dtype=torch.float32)
            dummy_aud = {"waveform": torch.zeros((1, 2, 48000), dtype=torch.float32), "sample_rate": 48000}
            status_str = f"Emitted conditioning for {len(clips)} clip(s) ({total_frames} frames @ {frame_rate} fps)."
            return (dummy_img, dummy_aud, None, last_positive, last_latent, last_prompt, float(frame_rate), int(total_frames), status_str)

        # Filter outputs based on preview_mode
        output_frames = all_decoded_frames
        output_audios = all_decoded_audios
        out_indices = list(range(len(clips)))

        if preview_mode in ("unvalidated", "unvalidated_only", "new_only"):
            unval_indices = [i for i, c in enumerate(clips) if not c.get("validated", False)]
            if unval_indices:
                output_frames = [all_decoded_frames[i] for i in unval_indices]
                output_audios = [all_decoded_audios[i] for i in unval_indices]
                out_indices = unval_indices
                log.info(f"Master Director: Preview Mode '{preview_mode}' active -> Outputting {len(unval_indices)} unvalidated clip(s).")
            else:
                log.info("Master Director: Preview Mode 'unvalidated' selected, but all clips are validated. Emitting full sequence.")

        # Stitch clips together
        if output_frames:
            target_h, target_w = output_frames[0].shape[1], output_frames[0].shape[2]
            standardized_frames = []
            standardized_audios = []
            for k, f in enumerate(output_frames):
                orig_idx = out_indices[k]
                curr_audio = output_audios[k] if k < len(output_audios) else None

                # Trim duplicate boundary frame and audio prefix if this clip was chained from the immediately preceding clip in output
                if k > 0 and orig_idx == out_indices[k - 1] + 1 and clip_chained_flags[orig_idx]:
                    f = trim_continuity_prefix(f, context_frames=1)
                    if curr_audio is not None:
                        curr_audio = trim_continuity_audio_prefix(curr_audio, context_frames=1)

                if curr_audio is not None:
                    standardized_audios.append(curr_audio)

                if f.shape[1] != target_h or f.shape[2] != target_w:
                    f_res = F.interpolate(f.permute(0, 3, 1, 2), size=(target_h, target_w), mode="bilinear", align_corners=False).permute(0, 2, 3, 1)
                    standardized_frames.append(f_res)
                else:
                    standardized_frames.append(f)
            final_frames = torch.cat(standardized_frames, dim=0)
            final_audio = concatenate_audio_clips(standardized_audios, target_sample_rate=48000) if standardized_audios else {"waveform": torch.zeros((1, 2, 48000)), "sample_rate": 48000}
        else:
            final_frames = torch.zeros((1, height, width, 3), dtype=torch.float32)
            final_audio = {"waveform": torch.zeros((1, 2, 48000)), "sample_rate": 48000}

        video_obj = {"images": final_frames, "fps": frame_rate, "audio": final_audio}
        status_str = f"Successfully generated {len(clips)} clip(s) -> {final_frames.shape[0]} total frames @ {frame_rate} fps (preview: {preview_mode})."
        return (
            final_frames,
            final_audio,
            video_obj,
            last_positive,
            last_latent,
            last_prompt,
            float(frame_rate),
            int(final_frames.shape[0]),
            status_str,
        )


class MiniMaxH3DirectorGuide:
    """DaSiWa Director Guide node: converts a guide dictionary or Master Director conditioning into positive conditioning and latent."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "guide": ("MINIMAX_H3_DIRECTOR_GUIDE", {"tooltip": "Guide emitted by MiniMax H3 Director."}),
                "clip": ("CLIP", {"tooltip": "CLIP model (Qwen3-VL)."}),
                "vae": ("VAE", {"tooltip": "Video VAE."}),
            },
            "optional": {
                "audio_vae": ("VAE", {"tooltip": "Audio VAE (required for REF2VA)."}),
            },
        }

    RETURN_TYPES = ("CONDITIONING", "LATENT")
    RETURN_NAMES = ("positive", "latent")
    FUNCTION = "build"
    CATEGORY = CATEGORY

    def build(self, guide, clip, vae, audio_vae=None):
        from ..core.executor import MasterDirectorExecutor
        executor = MasterDirectorExecutor()
        if isinstance(guide, dict) and "positive" in guide and "latent" in guide:
            return (guide["positive"], guide["latent"])

        mode = guide.get("mode", "FL2VA") if isinstance(guide, dict) else "FL2VA"
        prompt = guide.get("prompt", "") if isinstance(guide, dict) else ""
        w = int(guide.get("width", 1344)) if isinstance(guide, dict) else 1344
        h = int(guide.get("height", 768)) if isinstance(guide, dict) else 768
        dur = float(guide.get("duration", 5.0)) if isinstance(guide, dict) else 5.0

        pos, lat, _ = executor.build_conditioning(
            mode=mode,
            prompt=prompt,
            width=w,
            height=h,
            duration=dur,
            clip=clip,
            vae=vae,
            audio_vae=audio_vae,
        )
        return (pos, lat)


class MiniMaxH3DirectorPlannerConditioning:
    """Official MiniMax H3 conditioning plus task_mode string for planning UIs."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "guide": ("MINIMAX_H3_DIRECTOR_GUIDE", {"tooltip": "Guide emitted by MiniMax H3 Director."}),
                "clip": ("CLIP", {"tooltip": "CLIP model (Qwen3-VL)."}),
                "vae": ("VAE", {"tooltip": "Video VAE."}),
            },
            "optional": {
                "audio_vae": ("VAE", {"tooltip": "Audio VAE (required for REF2VA)."}),
            },
        }

    RETURN_TYPES = ("CONDITIONING", "LATENT", "STRING")
    RETURN_NAMES = ("positive", "latent", "task_mode")
    FUNCTION = "build"
    CATEGORY = CATEGORY

    def build(self, guide, clip, vae, audio_vae=None):
        guide_node = MiniMaxH3DirectorGuide()
        pos, lat = guide_node.build(guide, clip, vae, audio_vae=audio_vae)
        mode = guide.get("mode", "FL2VA") if isinstance(guide, dict) else "FL2VA"
        return (pos, lat, mode)

