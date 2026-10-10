"""Primary custom node: MiniMax H3 Master Director."""

from __future__ import annotations

import json
import logging
import math
from typing import Any, Dict, List, Optional

import torch
import torch.nn.functional as F

try:
    from ..core.config import FPS, CANVAS_MULTIPLE, align_frame_count
    from ..core.task_modes import MODE_INPAINT, normalize_mode, get_required_model_type
    from ..core.refmod import process_refmod_rows, build_refmod_tag_map, translate_refmod_aliases
    from ..core.prompt_engine import build_keyframe_mode_prompt, build_ref2va_prompt
    from ..core.continuity import trim_continuity_prefix, trim_continuity_audio_prefix, match_color_temperature_and_grade, extract_streams_from_av_latent
    from ..core.executor import (
        MasterDirectorExecutor,
        decode_video_latent,
        decode_audio_latent,
    )
    from ..core.refine import apply_refine_pass
    from ..core.audio_post import concatenate_audio_clips
    from ..core.cache_manager import compute_clip_fingerprint
except (ImportError, ValueError):
    from core.config import FPS, CANVAS_MULTIPLE, align_frame_count
    from core.task_modes import MODE_INPAINT, normalize_mode, get_required_model_type
    from core.refmod import process_refmod_rows, build_refmod_tag_map, translate_refmod_aliases
    from core.prompt_engine import build_keyframe_mode_prompt, build_ref2va_prompt
    from core.continuity import trim_continuity_prefix, trim_continuity_audio_prefix, match_color_temperature_and_grade, extract_streams_from_av_latent
    from core.executor import (
        MasterDirectorExecutor,
        decode_video_latent,
        decode_audio_latent,
    )
    from core.refine import apply_refine_pass
    from core.audio_post import concatenate_audio_clips
    from core.cache_manager import compute_clip_fingerprint

log = logging.getLogger("MiniMaxH3MasterDirector.node")

try:
    from ..core.sampling import sample_latent, native_outputs
    from ..core.cache_manager import fingerprint_value
    from ..core.audio_post import fit_audio_duration
    from ..core.loras import resolve_lora_files, apply_loras
    from ..core.source_media import source_range, choose_audio
    from ..core.advanced_sampling import sample_selflift
    from ..core.project import migrate_timeline, save_autosave
    from ..core.references import load_reference, edit_images
except ImportError:
    from core.sampling import sample_latent, native_outputs
    from core.cache_manager import fingerprint_value
    from core.audio_post import fit_audio_duration
    from core.loras import resolve_lora_files, apply_loras
    from core.source_media import source_range, choose_audio
    from core.advanced_sampling import sample_selflift
    from core.project import migrate_timeline, save_autosave
    from core.references import load_reference, edit_images

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
                "prompt_text": ("STRING", {"forceInput": True, "tooltip": "Newline-separated shot prompts from any text node. Blank lines are ignored."}),
                "model_pack": ("MMX_MODEL_PACK", {"tooltip": "Named models for per-shot overrides."}),
                "continuation": ("MMX_CONTINUATION", {"tooltip": "Explicitly selected take/checkpoint to continue."}),
                "timeline_data": ("STRING", {"default": "{\"version\":1,\"clips\":[]}", "multiline": False}),
                "builder_state": ("STRING", {"default": "{}", "multiline": False}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "prompt": "PROMPT",
            },
        }

    RETURN_TYPES = ("IMAGE", "AUDIO", "VHS_VIDEOINFO", "CONDITIONING", "LATENT", "STRING", "FLOAT", "INT", "STRING", "STRING")
    RETURN_NAMES = ("images", "audio", "video", "positive", "latent", "resolved_prompt", "fps", "frame_count", "status", "project_state")
    FUNCTION = "execute"
    OUTPUT_NODE = False
    CATEGORY = CATEGORY

    @classmethod
    def check_lazy_status(
        cls,
        model=None,
        fl2va_model=None,
        ref2va_model=None,
        timeline_data="{}",
        config=None,
        **kwargs,
    ):
        """Determine which model inputs need evaluation based on active timeline clip modes."""
        settings = config if isinstance(config, dict) else {}
        if kwargs.get("execution_mode", settings.get("execution_mode")) == "Conditioning Guide Output":
            return []
        if model is not None:
            return []
        if kwargs.get("model_pack"):
            return []

        try:
            tl = json.loads(timeline_data or "{}") if isinstance(timeline_data, str) else timeline_data
            clips = tl.get("clips", []) if isinstance(tl, dict) else []
            if clips:
                types = {normalize_mode(c.get("type", "T2V")) for c in clips}
            else:
                types = set()
        except Exception:
            types = set()

        if not types:
            return ["model"] if model is None else []

        needs_fl2va = any(get_required_model_type(t) == "fl2va" for t in types)
        needs_ref2va = any(get_required_model_type(t) == "ref2va" for t in types)

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
        prompt_text=None,
        model_pack=None,
        continuation=None,
        timeline_data="{}",
        builder_state="{}",
        unique_id="default_director",
        **kwargs,
    ):
        try:
            from ..core.provenance import record_graph_provenance
        except ImportError:
            from core.provenance import record_graph_provenance
        record_graph_provenance(kwargs.get("prompt"), unique_id,
            model=model, fl2va_model=fl2va_model, ref2va_model=ref2va_model,
            clip=clip, video_vae=video_vae, audio_vae=audio_vae)
        # Extract execution mode first to determine if diffusion models are required
        cfg_dict = config if config and isinstance(config, dict) else {}
        exec_mode = str(
            kwargs.get("execution_mode")
            or cfg_dict.get("execution_mode")
            or "Full Generation"
        )
        if exec_mode != "Conditioning Guide Output" and model is None and fl2va_model is None and ref2va_model is None and not model_pack:
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
        if not math.isfinite(frame_rate) or frame_rate != FPS:
            raise ValueError("MiniMax H3 generation uses 24 fps. Change playback speed after generation.")
        if width < 32 or height < 32 or width % CANVAS_MULTIPLE or height % CANVAS_MULTIPLE:
            raise ValueError("Canvas dimensions must be positive multiples of 32 pixels.")
        steps = int(kwargs.get("steps", cfg_dict.get("steps", 25)))
        cfg = float(kwargs.get("cfg", cfg_dict.get("cfg", 1.0)))
        sampler = str(kwargs.get("sampler", cfg_dict.get("sampler", "res_multistep")))
        scheduler = str(kwargs.get("scheduler", cfg_dict.get("scheduler", "simple")))
        shift_video = float(kwargs.get("shift_video", cfg_dict.get("shift_video", 12.0)))
        shift_audio = float(kwargs.get("shift_audio", cfg_dict.get("shift_audio", 3.0)))
        seed = int(kwargs.get("seed", cfg_dict.get("seed", 0)))
        execution_mode = str(kwargs.get("execution_mode", cfg_dict.get("execution_mode", "All-in-One Generation")))
        prompt_mode = str(kwargs.get("prompt_mode", cfg_dict.get("prompt_mode", "structured")))
        run_mode = str(kwargs.get("run_mode", cfg_dict.get("run_mode", "full_batch")))
        continuity_mode = str(kwargs.get("continuity_mode", cfg_dict.get("continuity_mode", "Motion Context (Chained)")))
        context_length = str(kwargs.get("context_length", cfg_dict.get("context_length", "22")))
        prompt_value = kwargs.get("prompt", cfg_dict.get("prompt", ""))
        # ComfyUI's hidden PROMPT is the execution graph, not user prompt text.
        prompt = str(cfg_dict.get("prompt", "") if isinstance(prompt_value, dict) else prompt_value)
        mode = kwargs.get("mode", cfg_dict.get("mode", None))
        try:
            timeline = json.loads(timeline_data or "{}") if isinstance(timeline_data, str) else timeline_data
            if not isinstance(timeline, dict):
                raise ValueError("Timeline must be a JSON object.")
            authored_clips = "clips" in timeline
            timeline = migrate_timeline(timeline)
            if timeline.get("resolution"):
                try:
                    from ..core.resolution import plan_canvas, timeline_media_size
                except ImportError:
                    from core.resolution import plan_canvas, timeline_media_size
                source_size = timeline.get("source_size")
                if source_size is None and (timeline["resolution"].get("mode") == "original" or timeline["resolution"].get("aspect") == "auto"):
                    source_size = timeline_media_size(timeline)
                width, height = plan_canvas(timeline["resolution"], source_size)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("Timeline contains invalid JSON.") from exc

        try:
            builder = json.loads(builder_state or "{}") if isinstance(builder_state, str) else builder_state
            if not isinstance(builder, dict):
                builder = {}
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("Prompt builder contains invalid JSON.") from exc

        project_id = str(timeline.get("project_id") or cfg_dict.get("project_id") or unique_id or "default_director")
        timeline["project_id"] = project_id
        executor = MasterDirectorExecutor(project_id=project_id)

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

        refmod_items = process_refmod_rows(refmod_rows, strict=execution_mode != "Conditioning Guide Output") if refmod_rows else []
        # If files were not loaded from disk (e.g. mock or missing file), preserve metadata for tag translation
        if not refmod_items and refmod_rows:
            for r in refmod_rows:
                if not isinstance(r, dict) or not r.get("enabled", True) or not r.get("name"):
                    continue
                slot = r.get("slot", len(refmod_items) + 1)
                refmod_items.append({
                    "id": f"mod_{slot}",
                    "slot": slot,
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
                        if "alt_id" in r:
                            ref_pool[r["alt_id"]] = r
                        if "slot_id" in r and (r.get("pack_index", 1) == 1 or r["slot_id"] not in ref_pool):
                            ref_pool[r["slot_id"]] = r
                        if "ref_id" in r:
                            ref_pool[r["ref_id"]] = r
            # Format 2: Bridge dict {"ref_image_1": ...}
            for k, v in ref_pack.items():
                if "refs" not in ref_pack and k not in ("refs", "pack_count", "version") and v is not None:
                    ref_pool[k] = {"id": k, "slot_id": k, "name": k, "type": "image", "data": v}

        # Parse clips from timeline
        timeline["width"] = width
        timeline["height"] = height
        for row in timeline.get("references", []):
            if not isinstance(row, dict) or not row.get("id"):
                raise ValueError("Uploaded references need a unique ID.")
            if row["id"] in ref_pool:
                raise ValueError(f"Duplicate uploaded reference ID: {row['id']}")
            ref_pool[row["id"]] = {**row, "file_reference": True}
        file_reference_cache = {}
        clips = timeline.get("clips", [])
        if i2v_groups is not None or r2v_groups is not None:
            from .node_groups import _normalize_group
            clips = []
            for group in _normalize_group(i2v_groups) + _normalize_group(r2v_groups):
                clips.append({"id": f"group_{len(clips) + 1}", "type": group.get("kind", "REF2VA"),
                    "duration": group.get("duration_sec", duration), "prompt": group.get("prompt", ""),
                    "group": group, "continuity": False})
        if prompt_text is not None:
            prompts = [line.strip() for line in str(prompt_text).splitlines() if line.strip()]
            if not isinstance(prompts, list):
                raise ValueError("Prompt pack must contain a prompts list.")
            if clips:
                clips = [{**item, "prompt": prompts[i]} if i < len(prompts) else dict(item) for i, item in enumerate(clips)]
            else:
                clips = [{"id": f"prompt_{i+1}", "type": mode or "T2VA", "duration": duration, "prompt": value} for i, value in enumerate(prompts)]
        if not clips:
            if authored_clips:
                raise ValueError("The timeline has no shots. Click + Add Shot before running.")
            # Fallback single clip if timeline has no clips
            default_type = mode if mode else ("REF2VA" if ref_pool else "T2V")
            clips = [{
                "id": "clip_1",
                "name": "Shot 1",
                "type": default_type,
                "duration": duration,
                "prompt": prompt,
                "ref_ids": list(dict.fromkeys(r.get("id", key) for key, r in ref_pool.items())),
                "continuity": True,
            }]

        if not isinstance(clips, list) or any(not isinstance(item, dict) for item in clips):
            raise ValueError("Timeline clips must be a list of shot objects.")
        clip_ids = [str(item.get("id") or f"clip_{i+1}") for i, item in enumerate(clips)]
        if len(set(clip_ids)) != len(clip_ids):
            raise ValueError("Every timeline shot must have a unique clip ID.")

        cache_mgr = executor.cache_mgr
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
        previous_fingerprint = None
        generated_count = 0
        completed_clips = []
        lora_state_cache = {}
        try:
            from ..core.provenance import runtime_provenance, algorithm_provenance
        except ImportError:
            from core.provenance import runtime_provenance, algorithm_provenance
        runtime_signature = runtime_provenance()
        try:
            from ..core.progress import shot_event
        except ImportError:
            from core.progress import shot_event
        run_report = []
        algorithm_signature = algorithm_provenance(selflift, refine, semantic_bridge) if execution_mode != "Conditioning Guide Output" else []
        low_carry = None
        previous_av = None
        if continuation is not None:
            previous_av = continuation.get("latent")
            frames = continuation.get("frames")
            if frames is None or frames.shape[0] < 1:
                raise ValueError("Continuation checkpoint has no decoded frames.")
            previous_tail = {"last_frame": frames[-1:], "tail_frames": frames[-min(56, frames.shape[0]):],
                "tail_audio": continuation.get("audio"), "tail_latent": None}
            previous_fingerprint = fingerprint_value([previous_av, frames, continuation.get("audio")])

        for clip_idx, clip_item in enumerate(clips):
            clip_id = str(clip_item.get("id") or f"clip_{clip_idx + 1}")
            clip_type = str(clip_item.get("type", "T2V")).upper()
            clip_dur = float(clip_item.get("duration", duration))
            if not math.isfinite(clip_dur) or clip_dur <= 0:
                raise ValueError(f"Shot {clip_idx + 1} duration must be positive and finite.")
            clip_prompt_text = str(clip_item.get("prompt", "") or prompt or "")
            clip_continuity = bool(clip_item.get("continuity", True)) and continuity_mode != "Independent (No Continuity)"
            clip_ref_ids = clip_item.get("ref_ids", [])
            clip_ref_ids = list(dict.fromkeys([*timeline.get("shared_ref_ids", []), *clip_ref_ids]))
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
            authored_seed = str(clip_seed)
            seed_mode = clip_item.get("seed_mode", "fixed")
            if seed_mode not in ("fixed", "randomize", "increment", "decrement"):
                raise ValueError("Unknown shot seed mode.")
            skipping_selection = bool(timeline.get("run_selection", False)) and not clip_item.get("selected", True)
            if (clip_validated or skipping_selection) and clip_item.get("last_seed") is not None:
                clip_seed = int(clip_item["last_seed"])
            elif seed_mode == "randomize" and execution_mode != "Conditioning Guide Output":
                import secrets
                clip_seed = secrets.randbits(64)

            # Map clip_type to canonical MiniMax mode (unifying REF2V into REF2VA)
            canon_mode = normalize_mode(clip_type)
            if canon_mode == MODE_INPAINT:
                clip_continuity = False
                clip_dur = 5 / FPS
            clip_lora_files = resolve_lora_files(clip_item.get("loras", [])) if clip_item.get("loras") else []

            # Select model for this clip
            clip_active_model = fl2va_model if get_required_model_type(canon_mode) == "fl2va" else ref2va_model
            if clip_active_model is None:
                clip_active_model = model
            if clip_item.get("model_override"):
                clip_active_model = (model_pack or {}).get(clip_item["model_override"])
                if clip_active_model is None:
                    raise ValueError(f"Unknown shot model override: {clip_item['model_override']}")
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
            local_video_audios = {}
            seen_refs = set()
            for rid in clip_ref_ids:
                robj = ref_pool.get(rid)
                if not robj:
                    raise ValueError(f"Shot {clip_idx + 1}: reference {rid!r} is not connected.")
                if robj.get("file_reference"):
                    if rid not in file_reference_cache:
                        import folder_paths
                        file_reference_cache[rid] = load_reference(robj, folder_paths.get_input_directory(), width, height)
                    loaded = file_reference_cache[rid]
                    for entry in loaded:
                        if entry["type"] == "image": local_imgs.append(entry["data"])
                        elif entry["type"] == "video": local_vids.append(entry["data"])
                        elif entry["type"] == "audio":
                            if entry.get("paired_video_id"):
                                local_video_audios[f"ref_video_{len(local_vids)}"] = entry["data"]
                            else: local_auds.append(entry["data"])
                    continue
                identity = robj.get("id", rid)
                if identity in seen_refs:
                    continue
                seen_refs.add(identity)
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
            ref_video_audios = dict(local_video_audios)
            group = clip_item.get("group", {})
            guide_frames = None

            # Automatic internal continuity: inject previous clip's tail frame
            is_chained_from_previous = False
            if clip_continuity and previous_tail is not None:
                first_frame = previous_tail["last_frame"]
                is_chained_from_previous = True

            if canon_mode == MODE_INPAINT:
                try:
                    from ..core.task_modes import validate_mode_assets
                except ImportError:
                    from core.task_modes import validate_mode_assets
                validate_mode_assets(canon_mode, images=local_imgs, videos=local_vids,
                    audios=local_auds, raise_on_error=True)
                first_frame = local_imgs[0]
                last_frame = None
                is_chained_from_previous = False
            elif canon_mode == "I2VA":
                if local_imgs:
                    first_frame = local_imgs[0]
                    is_chained_from_previous = False
            elif canon_mode == "L2VA":
                if local_imgs:
                    last_frame = local_imgs[0]
                first_frame = None
                is_chained_from_previous = False
            elif canon_mode == "FL2VA":
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
            elif canon_mode in ("V2V", "REF2VA", "RV2V"):
                first_frame = None
                for i, img in enumerate(local_imgs):
                    ref_images[f"ref_image_{i+1}"] = img
                for i, v in enumerate(local_vids):
                    ref_videos[f"ref_video_{i+1}"] = v
                for i, a in enumerate(local_auds):
                    ref_audios[f"ref_audio_{i+1}"] = a

                # Automatic internal continuity for reference modes: if no local visual references were assigned, inject tail
                if clip_continuity and previous_tail is not None and clip_idx > 0:
                    if not ref_images and not ref_videos and previous_tail.get("last_frame") is not None:
                        ref_images["ref_image_1"] = previous_tail["last_frame"]
                    if not ref_audios and previous_tail.get("tail_audio") is not None:
                        ref_audios["ref_audio_1"] = previous_tail["tail_audio"]
                is_chained_from_previous = False


            clip_chained_flags[clip_idx] = is_chained_from_previous
            if group:
                first_frame = group.get("first_frame", first_frame)
                last_frame = group.get("last_frame", last_frame)
                ref_images = group.get("ref_images", ref_images)
                ref_videos = group.get("ref_videos", ref_videos)
                ref_audios = group.get("ref_audios", ref_audios)
                ref_video_audios = group.get("ref_video_audios", ref_video_audios)
            source = source_range(clip_item, timeline, width, height) if canon_mode in ("V2V", "RV2V") else None
            if source is not None:
                ref_video_audios = {f"ref_video_{i+2}": ref_video_audios[key] for i, key in enumerate(ref_videos) if key in ref_video_audios}
                ref_videos = {"ref_video_1": source["frames"],
                    **{f"ref_video_{i+2}": value for i, value in enumerate(ref_videos.values())}}
                clip_dur = source["frames"].shape[0] / FPS
                # Source coordinates define the visible edit range. Prefix
                # guides would consume part of that range during assembly.
                guide_frames = None
                is_chained_from_previous = False
                clip_chained_flags[clip_idx] = False
            audio_mode = clip_item.get("audio_mode", timeline.get("audio_mode", "generate"))
            visible_frames = source["frames"].shape[0] if source is not None else align_frame_count(int(clip_dur * FPS))
            continuation_prefix = 0
            latent_carry = continuity_mode == "Latent Carry (Pinned)"
            if source is None and canon_mode != MODE_INPAINT and clip_continuity and previous_tail is not None:
                frames = previous_tail.get("tail_frames")
                if frames is not None and frames.shape[0] >= 5 and continuity_mode in ("Motion Context (Chained)", "Latent Carry (Pinned)"):
                    count = align_frame_count(min(int(context_length), int(frames.shape[0])), "down")
                    continuation_prefix = count
                    clip_dur = align_frame_count(visible_frames + count) / FPS
                    if not latent_carry:
                        guide_audio = previous_tail.get("tail_audio")
                        if guide_audio is not None:
                            guide_audio = {**guide_audio, "waveform": guide_audio["waveform"][..., -round(count/FPS*guide_audio["sample_rate"]):]}
                        guide_frames = [{"frame": frames[-count:], "frame_idx": 0, "audio": guide_audio}]
                    if first_frame is not None and not is_chained_from_previous:
                        guide_frames = [*(guide_frames or []), {"frame": first_frame, "frame_idx": count}]
                    first_frame = None
                    if last_frame is not None:
                        guide_frames = [*(guide_frames or []), {"frame": last_frame, "frame_idx": count+visible_frames-1}]
                        last_frame = None
                    is_chained_from_previous = count
                    clip_chained_flags[clip_idx] = count
            if clip_item.get("locked"):
                if source is None:
                    raise ValueError("Locked source shots require a real source video range.")
                frames = source["frames"]
                audio = choose_audio("mute" if str(audio_mode).lower() == "mute" else "source", source["audio"], source, frames.shape[0])
                all_decoded_frames.append(frames); all_decoded_audios.append(audio); completed_clips.append(clip_item)
                clip_chained_flags[clip_idx] = False
                previous_tail = {"last_frame": frames[-1:], "tail_frames": frames[-min(56, frames.shape[0]):], "tail_audio": audio, "tail_latent": None}
                previous_av = None
                previous_fingerprint = fingerprint_value([frames, audio])
                run_report.append({"clip_id": clip_id, "action": "source", "frames": int(frames.shape[0])})
                continue
            try:
                from ..core.task_modes import validate_mode_assets
            except ImportError:
                from core.task_modes import validate_mode_assets
            if canon_mode in ("REF2VA", "V2V", "RV2V"):
                validate_mode_assets(canon_mode,
                    images=list(ref_images.values()) + [m for m in refmod_items if m.get("kind") == "image"],
                    videos=list(ref_videos.values()) + [m for m in refmod_items if m.get("kind") == "video"],
                    audios=list(ref_audios.values()) + [m for m in refmod_items if m.get("kind") == "audio"],
                    raise_on_error=True)

            # Build prompt (supporting per-clip structured prompts or raw prompts)
            tag_map = build_refmod_tag_map(refmod_items, len(ref_images), len(ref_videos), len(ref_audios))
            clip_prompt_mode = clip_item.get("prompt_mode", prompt_mode)
            clip_structured = clip_item.get("structured_prompt")

            if clip_prompt_mode == "structured" and isinstance(clip_structured, dict) and any(str(v).strip() for v in clip_structured.values()):
                c_soundscape = clip_structured.get("overall_soundscape") or clip_structured.get("soundscape", "")
                c_music = clip_structured.get("non_diegetic_music") or clip_structured.get("music", "")
                if canon_mode in ("REF2VA", "V2V", "RV2V"):
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
            elif canon_mode in ("REF2VA", "V2V", "RV2V"):
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
                    prompt_mode=clip_prompt_mode,
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
                    prompt_mode=clip_prompt_mode,
                )

            try:
                from ..core.prompt_engine import clean_mentions
            except ImportError:
                from core.prompt_engine import clean_mentions
            shared_prompt = str(timeline.get("shared_prompt", "")).strip()
            policy = timeline.get("shared_prompt_policy", "prepend")
            if policy not in ("prepend", "append"):
                raise ValueError("Shared prompt policy must be prepend or append.")
            if shared_prompt:
                resolved_prompt = "\n".join([shared_prompt, resolved_prompt] if policy == "prepend" else [resolved_prompt, shared_prompt])
            resolved_prompt = clean_mentions(resolved_prompt)
            for guide in clip_item.get("guides", []):
                rid = guide.get("ref_id")
                ref = ref_pool.get(rid)
                if ref is None: raise ValueError(f"Unknown guide reference: {rid}")
                if ref.get("file_reference"):
                    if rid not in file_reference_cache:
                        import folder_paths
                        file_reference_cache[rid] = load_reference(ref, folder_paths.get_input_directory(), width, height)
                    values = file_reference_cache[rid]
                else: values = [ref]
                anchor = {"frame_idx": continuation_prefix + round(float(guide.get("time", 0)) * FPS)}
                for value in values:
                    if value["type"] in ("image", "video"): anchor["frame"] = value.get("data")
                    elif value["type"] == "audio": anchor["audio"] = value.get("data")
                guide_frames = [*(guide_frames or []), anchor]

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
                ref_video_audios=ref_video_audios,
                refmod_items=refmod_items,
                guide_frames=guide_frames,
            )

            # Apply Semantic Bridge if wired
            if semantic_bridge is not None:
                try:
                    from .node_semantic_bridge import apply_semantic_bridge
                    positive = apply_semantic_bridge(positive, semantic_bridge, task_key=canon_mode)
                except Exception as exc:
                    raise RuntimeError(f"Enabled Semantic Bridge failed: {exc}") from exc

            previous_trim = 0
            if latent_carry and continuation_prefix:
                try:
                    from ..core.vendor.aimixer.director.h3_latent_continue import apply_latent_continue
                except ImportError:
                    from core.vendor.aimixer.director.h3_latent_continue import apply_latent_continue
                latent, trim_count, previous_trim = apply_latent_continue(latent,
                    prev_av=previous_av, prev_tail=previous_tail["tail_frames"], vae=video_vae,
                    context_length=continuation_prefix,
                    context_end_frame=previous_av.get("_mmx_visible_end") if previous_av else None,
                    context_audio=previous_tail.get("tail_audio"), audio_vae=audio_vae,
                    seam_min_mask=clip_item.get("continuity_redraw", timeline.get("continuity_redraw", .1)))
                is_chained_from_previous = trim_count
                clip_chained_flags[clip_idx] = trim_count
                if previous_trim and all_decoded_frames:
                    all_decoded_frames[-1] = all_decoded_frames[-1][:-previous_trim]
                    all_decoded_audios[-1] = fit_audio_duration(all_decoded_audios[-1], all_decoded_frames[-1].shape[0], FPS)
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
                model_name=str(getattr(clip_active_model, "model_name", "h3")),
                loras=clip_lora_files,
                ref_signatures=[fingerprint_value([ref_images, ref_videos, ref_video_audios, ref_audios, refmod_items, first_frame, last_frame])],
                upstream_fingerprint=previous_fingerprint if clip_continuity else None,
                generation_settings={"version": 3, "runtime": runtime_signature, "algorithm_weights": algorithm_signature, "mode": canon_mode, "steps": steps, "cfg": cfg,
                    "sampler": sampler, "scheduler": scheduler, "shift_video": shift_video,
                    "shift_audio": shift_audio, "selflift": selflift, "refine": refine,
                    "face_refine": face_refine, "semantic_bridge": semantic_bridge, "sigmas": sigmas,
                    "continuity_mode": continuity_mode, "context_length": context_length,
                    "tail_seconds": clip_tail_sec, "guides": guide_frames, "model": clip_active_model,
                    "audio_mode": audio_mode, "source_audio": source["audio"] if source is not None else None,
                    "video_vae": video_vae, "audio_vae": audio_vae, "clip": clip},
            )
            previous_fingerprint = clip_fp
            completed_clips.append(clip_item)

            # If clip is validated and stored in server cache, skip diffusion sampling!
            skip_requested = bool(timeline.get("run_selection", False)) and not clip_item.get("selected", True)
            if (clip_validated or skip_requested) and cache_mgr.is_clip_cached_and_valid(clip_id, clip_fp):
                cached_frames = cache_mgr.load_clip_frames(clip_id)
                cached_audio = cache_mgr.load_clip_audio(clip_id)
                cached_latent = cache_mgr.load_clip_latent(clip_id)
                if cached_frames is not None and cached_latent is not None and cached_audio is not None:
                    last_latent = cached_latent
                    previous_av = cached_latent
                    low_carry = cached_latent.get("_selflift_low_carry")
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
                    run_report.append({"clip_id": clip_id, "action": "cached", "frames": int(cached_frames.shape[0])})
                    continue

            if skip_requested:
                low_carry = None
                if source is None:
                    raise ValueError(f"Unselected shot {clip_id!r} has no matching cache or real source range to fill it.")
                frames = source["frames"]
                audio = choose_audio("mute" if str(audio_mode).lower() == "mute" else "source",
                    source["audio"], source, frames.shape[0])
                all_decoded_frames.append(frames)
                all_decoded_audios.append(audio)
                clip_chained_flags[clip_idx] = False
                previous_tail = {"last_frame": frames[-1:].clone(), "tail_frames": frames[-min(56, frames.shape[0]):].clone(),
                    "tail_audio": audio, "tail_latent": None}
                previous_fingerprint = fingerprint_value([frames, audio])
                run_report.append({"clip_id": clip_id, "action": "source", "frames": int(frames.shape[0])})
                continue

            # Sampling
            shot_event(unique_id, project_id, clip_id, "sampling", index=clip_idx+1, total=len(clips), seed=str(clip_seed))
            clip_active_model = apply_loras(clip_active_model, clip_lora_files, lora_state_cache)

            try:
                from comfy_extras.nodes_minimax_h3 import MiniMaxH3SigmaShift
                shifted_model, = native_outputs(MiniMaxH3SigmaShift.execute(clip_active_model, float(shift_video), float(shift_audio)))
            except ImportError as exc:
                raise RuntimeError("Update ComfyUI: native MiniMaxH3SigmaShift is required for correct AV sampling.") from exc

            # CFG > 1 needs a valid unconditional branch with the same H3 payload.
            negative = [[torch.zeros_like(emb), dict(meta)] for emb, meta in positive]
            clip_frames_count = align_frame_count(int(clip_dur * frame_rate))
            log.info(f"Master Director: Sampling clip {clip_idx + 1}/{len(clips)} [{clip_type} -> {canon_mode}] ({clip_frames_count} frames, seed={clip_seed})...")

            if selflift is not None and selflift.get("enabled", False):
                sampled_latent, low_carry = sample_selflift(
                    model=clip_active_model,
                    positive=positive,
                    negative=negative,
                    latent=latent,
                    seed=clip_seed,
                    steps=steps,
                    cfg=cfg,
                    settings=selflift, video_vae=video_vae, width=width, height=height,
                    shift_video=shift_video, shift_audio=shift_audio,
                    carry=low_carry if clip_continuity else None,
                    pin_frames=int(is_chained_from_previous) if continuation_prefix else 0,
                    sampler=sampler,
                    scheduler=scheduler,
                    sigmas=sigmas,
                )
                if low_carry is not None:
                    sampled_latent = {**sampled_latent, "_selflift_low_carry": low_carry}
            else:
                sampling_function = sample_latent
                if latent_carry and continuation_prefix:
                    try:
                        from ..core.advanced_sampling import sample_stage
                    except ImportError:
                        from core.advanced_sampling import sample_stage
                    sampling_function = sample_stage
                sampled_latent = sampling_function(
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
                    sigmas=sigmas,
                )

            # Optional second-pass Refine
            pre_refine_latent = sampled_latent
            if refine is not None and refine.get("enabled", False):
                refine_model = refine.get("refine_model")
                if refine_model is not None:
                    refine_model, = native_outputs(MiniMaxH3SigmaShift.execute(refine_model, shift_video, shift_audio))
                sampled_latent = apply_refine_pass(
                    model=shifted_model,
                    latent_dict=sampled_latent,
                    positive=positive,
                    negative=negative,
                    seed=clip_seed,
                    refine_mode=refine.get("mode", "refine"),
                    target_width=refine.get("target_width", width),
                    target_height=refine.get("target_height", height),
                    steps=refine.get("steps", 3),
                    cfg=refine.get("cfg", cfg),
                    refine_model=refine_model,
                    denoise=refine.get("denoise", 0.45),
                    enable_tiling=refine.get("enable_tiling", False),
                    tile_count=refine.get("tile_count", 2),
                    tile_overlap=refine.get("tile_overlap", 128),
                    sampler_name=refine.get("sampler", sampler), scheduler=refine.get("scheduler", scheduler),
                    sigmas=refine.get("sigmas"), passes=refine.get("passes", 1),
                    latent_upscale_model=refine.get("latent_upscale_model"),
                    enable_chunking=refine.get("enable_latent_chunking", False),
                    refine_backend=refine.get("backend", "global"), memory_budget_mb=refine.get("memory_budget_mb", 0),
                    video_vae=video_vae, first_frame=first_frame, last_frame=last_frame,
                    upscale_precision=refine.get("upscale_precision", "auto"),
                )

            # Decode
            previous_av = sampled_latent
            last_latent = sampled_latent
            v_stream, a_stream = extract_streams_from_av_latent(sampled_latent)
            decoded_frames = decode_video_latent(video_vae, v_stream)
            if source is not None:
                decoded_frames = decoded_frames[:source["frames"].shape[0]]
            elif continuation_prefix:
                decoded_frames = decoded_frames[:int(is_chained_from_previous)+visible_frames]
            sampled_latent["_mmx_visible_end"] = int(decoded_frames.shape[0])
            decoded_audio = decode_audio_latent(audio_vae, a_stream) if audio_vae else {"waveform": torch.zeros((1, 2, 48000)), "sample_rate": 48000}
            decoded_audio = fit_audio_duration(decoded_audio, decoded_frames.shape[0], FPS)
            decoded_audio = choose_audio(audio_mode, decoded_audio, source, decoded_frames.shape[0])
            if canon_mode == MODE_INPAINT:
                # Match DaSiWa's one-image / five-frame native workflow, with
                # the generated final frame exposed directly as a still.
                decoded_frames = decoded_frames[-1:]
                decoded_audio = {"waveform": torch.zeros((1, 2, round(48000 / FPS))), "sample_rate": 48000}

            # Continuity Seam Color Grading
            decoded_frames = edit_images(decoded_frames, clip_item.get("color"))
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
                try:
                    from ..core.tracked_face import refine_tracked_faces
                except ImportError:
                    from core.tracked_face import refine_tracked_faces
                decoded_frames, face_report = refine_tracked_faces(decoded_frames, shifted_model,
                    video_vae, audio_vae, clip, clip_seed, face_refine, cfg,
                    ref_images=ref_images, continuity=clip_continuity)

            all_decoded_frames.append(decoded_frames)
            all_decoded_audios.append(decoded_audio)

            # Store result in cache manager
            cache_error = None
            try:
                before_frames = None
                if refine is not None and refine.get("enabled", False):
                    before_video, _ = extract_streams_from_av_latent(pre_refine_latent)
                    before_frames = decode_video_latent(video_vae, before_video)
                    before_frames = before_frames[:decoded_frames.shape[0]]
                cache_mgr.store_clip_results(
                    clip_id=clip_id,
                    fingerprint=clip_fp,
                    latent_dict=sampled_latent,
                    audio_dict=decoded_audio,
                    decoded_frames=decoded_frames,
                    validated=clip_validated,
                    pre_refine_frames=before_frames,
                )
                cache_mgr.update_clip_metadata(clip_id, {"trim_prefix": int(is_chained_from_previous), "previous_trim": int(previous_trim), "seed": str(clip_seed), "mode": canon_mode})
            except Exception as c_err:
                cache_error = str(c_err)
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
            generated_count += 1
            clip_item["last_seed"] = str(clip_seed)
            clip_item["seed"] = str((clip_seed + (1 if seed_mode == "increment" else -1 if seed_mode == "decrement" else 0)) & 0xFFFFFFFFFFFFFFFF)
            timeline["builder_state"] = builder
            timeline["clips"] = clips
            save_autosave(cache_mgr, timeline)
            run_report.append({"clip_id": clip_id, "action": "generated", "seed": str(clip_seed),
                "frames": int(decoded_frames.shape[0]), "trim_prefix": int(is_chained_from_previous),
                "refine": sampled_latent.get("_mmx_refine_report", "off"), "cache_error": cache_error})
            shot_event(unique_id, project_id, clip_id, "completed", seed=str(clip_seed), next_seed=clip_item["seed"], authored_seed=authored_seed, index=clip_idx+1, total=len(clips))
            if run_mode == "clip_by_clip":
                break

        # Handle outputs
        if execution_mode == "Conditioning Guide Output":
            total_frames = 5 if canon_mode == MODE_INPAINT else align_frame_count(int(float(clips[-1].get("duration", duration)) * FPS))
            dummy_img = torch.zeros((1, height, width, 3), dtype=torch.float32)
            dummy_aud = {"waveform": torch.zeros((1, 2, 48000), dtype=torch.float32), "sample_rate": 48000}
            status_str = f"Emitted conditioning for {len(clips)} clip(s); returning final shot ({total_frames} frames @ {frame_rate} fps). Multi-shot chaining requires generation."
            return (dummy_img, dummy_aud, None, last_positive, last_latent, last_prompt, float(frame_rate), int(total_frames), status_str, json.dumps(timeline, ensure_ascii=False))

        # Filter outputs based on preview_mode
        output_frames = all_decoded_frames
        output_audios = all_decoded_audios
        clips = completed_clips
        out_indices = list(range(len(clips)))

        if preview_mode in ("unvalidated", "unvalidated_only", "new_only", "selected", "selected_only"):
            unval_indices = [i for i, c in enumerate(clips) if c.get("selected", True)] if preview_mode in ("selected", "selected_only") else [i for i, c in enumerate(clips) if not c.get("validated", False)]
            if unval_indices:
                output_frames = [all_decoded_frames[i] for i in unval_indices]
                output_audios = [all_decoded_audios[i] for i in unval_indices]
                out_indices = unval_indices
                log.info(f"Master Director: Preview Mode '{preview_mode}' active -> Outputting {len(unval_indices)} unvalidated clip(s).")
            else:
                if preview_mode in ("selected", "selected_only"):
                    raise ValueError("Selected-only output requires at least one selected shot.")
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
                if clip_chained_flags[orig_idx] and (int(clip_chained_flags[orig_idx]) > 1 or k > 0 and orig_idx == out_indices[k - 1] + 1):
                    prefix_count = int(clip_chained_flags[orig_idx])
                    f = trim_continuity_prefix(f, context_frames=prefix_count)
                    if curr_audio is not None:
                        curr_audio = trim_continuity_audio_prefix(curr_audio, context_frames=prefix_count)

                if curr_audio is not None:
                    standardized_audios.append(curr_audio)

                if f.shape[1] != target_h or f.shape[2] != target_w:
                    f_res = F.interpolate(f.permute(0, 3, 1, 2), size=(target_h, target_w), mode="bilinear", align_corners=False).permute(0, 2, 3, 1)
                    standardized_frames.append(f_res)
                else:
                    standardized_frames.append(f)
            final_frames = torch.cat(standardized_frames, dim=0)
            final_audio = concatenate_audio_clips(standardized_audios, target_sample_rate=48000, crossfade_ms=0,
                enable_gain_match=timeline.get("audio_gain_match", True), enable_declick=timeline.get("audio_fade_ms", 15) > 0,
                seam_fade_ms=float(timeline.get("audio_fade_ms", 15))) if standardized_audios else {"waveform": torch.zeros((1, 2, 48000)), "sample_rate": 48000}
        else:
            final_frames = torch.zeros((1, height, width, 3), dtype=torch.float32)
            final_audio = {"waveform": torch.zeros((1, 2, 48000)), "sample_rate": 48000}

        # VHS_VIDEOINFO is metadata, not a video container or image/audio bundle.
        video_obj = {}
        for prefix in ("source", "loaded"):
            video_obj.update({f"{prefix}_fps": frame_rate,
                f"{prefix}_frame_count": int(final_frames.shape[0]),
                f"{prefix}_duration": final_frames.shape[0] / frame_rate,
                f"{prefix}_width": int(final_frames.shape[2]),
                f"{prefix}_height": int(final_frames.shape[1])})
        status_str = json.dumps({"generated": generated_count, "output_frames": int(final_frames.shape[0]),
            "fps": frame_rate, "preview": preview_mode, "shots": run_report}, ensure_ascii=False)
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
            json.dumps(timeline, ensure_ascii=False),
        )
