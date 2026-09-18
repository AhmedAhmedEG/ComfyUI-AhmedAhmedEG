"""Primary custom node: MiniMax H3 Master Director."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import torch

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

log = logging.getLogger("MiniMaxH3MasterDirector.node")

CATEGORY = "ComfyUI-AhmedAhmedEG"


class MiniMaxH3MasterDirector:
    """Unified master director node combining multi-track authoring, prompt engineering, and AV generation."""

    @classmethod
    def INPUT_TYPES(cls):
        import comfy.samplers

        return {
            "required": {
                "model": ("MODEL", {"lazy": True, "tooltip": "MiniMax H3 diffusion model (or use fl2va_model / ref2va_model sockets)."}),
                "video_vae": ("VAE", {"tooltip": "MiniMax H3 Video VAE (minimax_h3_video_vae)."}),
                "audio_vae": ("VAE", {"tooltip": "MiniMax H3 Audio VAE (minimax_h3_audio_vae). Required for REF2VA & Audio."}),
                "clip": ("CLIP", {"tooltip": "MiniMax H3 Qwen3-VL CLIP model."}),
                "mode": (list(SUPPORTED_MODES), {"default": MODE_REF2VA, "tooltip": "Task mode"}),
                "execution_mode": (["All-in-One Generation", "Conditioning Guide Output"], {"default": "All-in-One Generation", "tooltip": "Choose between full in-node generation or emitting positive/latent for custom graphs."}),
                "width": ("INT", {"default": 1344, "min": 32, "max": 4096, "step": 32}),
                "height": ("INT", {"default": 768, "min": 32, "max": 4096, "step": 32}),
                "duration": ("FLOAT", {"default": 5.0, "min": 0.5, "max": 60.0, "step": 0.1}),
                "frame_rate": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 120.0, "step": 0.1}),
                "prompt": ("STRING", {"default": "", "multiline": True, "tooltip": "Scene description prompt"}),
                "prompt_mode": (["structured", "simple"], {"default": "structured"}),
                "run_mode": (["clip_by_clip", "full_batch"], {"default": "clip_by_clip"}),
                "continuity_mode": (["Motion Context (Chained)", "Independent (No Continuity)", "FL2VA Tail Handoff"], {"default": "Motion Context (Chained)"}),
                "context_length": (["22", "5", "39", "56"], {"default": "22"}),
                "steps": ("INT", {"default": 25, "min": 1, "max": 200, "step": 1}),
                "cfg": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 20.0, "step": 0.1}),
                "sampler": (comfy.samplers.KSampler.SAMPLERS, {"default": "res_multistep"}),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS, {"default": "simple"}),
                "shift_video": ("FLOAT", {"default": 12.0, "min": 0.1, "max": 100.0, "step": 0.1}),
                "shift_audio": ("FLOAT", {"default": 3.0, "min": 0.1, "max": 100.0, "step": 0.1}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
            },
            "optional": {
                "fl2va_model": ("MODEL", {"lazy": True, "tooltip": "Lazy-loaded FL2VA UNET."}),
                "ref2va_model": ("MODEL", {"lazy": True, "tooltip": "Lazy-loaded REF2VA UNET."}),
                "selflift": ("MMX_DIR_SELFLIFT", {"tooltip": "Optional SelfLift progressive sampling settings."}),
                "refine": ("MMX_DIR_REFINE", {"tooltip": "Optional 2nd-pass refine and upscale settings."}),
                "face_refine": ("MMX_DIR_FACE_REFINE", {"tooltip": "Optional FaceRefine close-up tracking & stitch."}),
                "sigmas": ("SIGMAS", {"forceInput": True, "tooltip": "External sigma schedule override."}),
                "ref_pack": ("REF_PACK", {"tooltip": "External reference pack bridge."}),
                "prompt_pack": ("PROMPT_PACK", {"tooltip": "External prompt pack bridge."}),
                "timeline_data": ("STRING", {"default": "{\"version\":1,\"clips\":[],\"tracks\":[]}", "multiline": False}),
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
        mode="REF2VA",
        model=None,
        fl2va_model=None,
        ref2va_model=None,
        **kwargs,
    ):
        """Lazy evaluate only the model required for active mode."""
        req_type = get_required_model_type(mode)
        if req_type == "fl2va":
            if fl2va_model is None and model is None:
                return ["fl2va_model"]
        else:
            if ref2va_model is None and model is None:
                return ["ref2va_model"]
        return []

    def execute(
        self,
        model=None,
        video_vae=None,
        audio_vae=None,
        clip=None,
        mode="REF2VA",
        execution_mode="All-in-One Generation",
        width=1344,
        height=768,
        duration=5.0,
        frame_rate=24.0,
        prompt="",
        prompt_mode="structured",
        run_mode="clip_by_clip",
        continuity_mode="Motion Context (Chained)",
        context_length="22",
        steps=25,
        cfg=1.0,
        sampler="res_multistep",
        scheduler="simple",
        shift_video=12.0,
        shift_audio=3.0,
        seed=0,
        fl2va_model=None,
        ref2va_model=None,
        selflift=None,
        refine=None,
        face_refine=None,
        sigmas=None,
        ref_pack=None,
        prompt_pack=None,
        timeline_data="{}",
        builder_state="{}",
        unique_id="default_director",
    ):
        canon_mode = normalize_mode(mode)
        active_model = fl2va_model if canon_mode in ("FL2VA", "I2VA", "L2VA", "T2VA", "Image Inpaint") and fl2va_model is not None else (
            ref2va_model if ref2va_model is not None else model
        )

        try:
            timeline = json.loads(timeline_data or "{}")
            if not isinstance(timeline, dict):
                timeline = {}
        except Exception:
            timeline = {}

        try:
            builder = json.loads(builder_state or "{}")
            if not isinstance(builder, dict):
                builder = {}
        except Exception:
            builder = {}

        executor = MasterDirectorExecutor(project_id=str(unique_id))

        # Check for RefMods
        refmod_rows = timeline.get("refmods", [])
        refmod_items = process_refmod_rows(refmod_rows) if canon_mode == "REF2VA" else []

        # Parse active media items from timeline
        items = timeline.get("items", [])
        input_directory = None
        try:
            import folder_paths
            input_directory = folder_paths.get_input_directory()
        except Exception:
            pass

        ref_images = {}
        ref_videos = {}
        ref_video_audios = {}
        ref_audios = {}
        first_frame = None
        last_frame = None

        for idx, item in enumerate(items):
            if not item.get("enabled", True):
                continue
            itype = item.get("type")
            val = item.get("value")
            if not val:
                continue

            t_start = float(item.get("trim_start", 0.0))
            t_end = float(item["trim_end"]) if item.get("trim_end") is not None else None

            if itype == "image":
                img_t = load_image(val, input_directory=input_directory, target_width=width, target_height=height)
                if canon_mode in ("I2VA", "FL2VA") and first_frame is None:
                    first_frame = img_t
                elif canon_mode in ("L2VA", "FL2VA") and last_frame is None and (first_frame is not None or canon_mode == "L2VA"):
                    last_frame = img_t
                elif canon_mode == "Image Inpaint":
                    first_frame = img_t
                else:
                    ref_images[f"ref_image_{len(ref_images) + 1}"] = img_t

            elif itype == "video":
                v_mode = item.get("media_mode", "video")
                if v_mode in ("video", "video_audio"):
                    vid_t = load_video(val, input_directory=input_directory, trim_start=t_start, trim_end=t_end, target_fps=frame_rate)
                    ref_videos[f"ref_video_{len(ref_videos) + 1}"] = vid_t
                if v_mode in ("audio", "video_audio"):
                    aud_t = load_embedded_video_audio(val, input_directory=input_directory, trim_start=t_start, trim_end=t_end)
                    if v_mode == "video_audio":
                        ref_video_audios[f"ref_video_audio_{len(ref_videos)}"] = aud_t
                    else:
                        ref_audios[f"ref_audio_{len(ref_audios) + 1}"] = aud_t

            elif itype == "audio":
                aud_t = load_audio(val, input_directory=input_directory, trim_start=t_start, trim_end=t_end)
                ref_audios[f"ref_audio_{len(ref_audios) + 1}"] = aud_t

        # Build prompt
        tag_map = build_refmod_tag_map(refmod_items, len(ref_images), len(ref_videos), len(ref_audios))
        if canon_mode == "REF2VA":
            ref_dict = builder.get("ref", {})
            resolved_prompt = build_ref2va_prompt(
                subject_definitions=translate_refmod_aliases(ref_dict.get("subject_definitions", ""), tag_map),
                summary=translate_refmod_aliases(ref_dict.get("summary", ""), tag_map),
                retention_analysis=translate_refmod_aliases(ref_dict.get("retention_analysis", ""), tag_map),
                detailed_description=translate_refmod_aliases(ref_dict.get("detailed_description", prompt), tag_map),
                soundscape=translate_refmod_aliases(ref_dict.get("soundscape", ""), tag_map),
                music=translate_refmod_aliases(ref_dict.get("music", ""), tag_map),
                prompt_mode=prompt_mode,
            )
        else:
            resolved_prompt = build_keyframe_mode_prompt(
                mode=canon_mode,
                imd=builder.get("imd", prompt),
                soundscape=builder.get("soundscape", ""),
                music=builder.get("music", ""),
                duration_sec=duration,
                has_first_frame=first_frame is not None,
                has_last_frame=last_frame is not None,
                prompt_mode=prompt_mode,
            )

        # Generate conditioning
        positive, latent, final_prompt = executor.build_conditioning(
            mode=canon_mode,
            prompt=resolved_prompt,
            width=width,
            height=height,
            duration=duration,
            clip=clip,
            vae=video_vae,
            audio_vae=audio_vae,
            first_frame=first_frame,
            last_frame=last_frame,
            ref_images=ref_images,
            ref_videos=ref_videos,
            ref_video_audios=ref_video_audios,
            ref_audios=ref_audios,
            refmod_items=refmod_items,
        )

        frame_count = align_frame_count(int(duration * frame_rate))

        # If Modular Conditioning Mode is selected, skip in-node sampling
        if execution_mode == "Conditioning Guide Output":
            dummy_img = torch.zeros((1, height, width, 3), dtype=torch.float32)
            dummy_aud = {"waveform": torch.zeros((1, 2, 48000), dtype=torch.float32), "sample_rate": 48000}
            status_str = f"Emitted conditioning for {canon_mode} ({frame_count} frames @ {frame_rate} fps)."
            return (dummy_img, dummy_aud, None, positive, latent, final_prompt, float(frame_rate), int(frame_count), status_str)

        # All-in-One Generation Mode: Run sampling
        import comfy.sample
        import comfy.samplers

        # Apply SigmaShift
        shifted_model = active_model.clone()
        shifted_model.model_options = dict(shifted_model.model_options or {})
        shifted_model.model_options["minimax_h3_sigma_shift_video"] = float(shift_video)
        shifted_model.model_options["minimax_h3_sigma_shift_audio"] = float(shift_audio)

        negative = []

        log.info(f"Master Director: Starting sampling pass for {canon_mode} ({frame_count} frames)...")
        if selflift is not None and selflift.get("enabled", False):
            sampled_latent = sample_selflift_progressive(
                model=shifted_model,
                positive=positive,
                negative=negative,
                latent_dict=latent,
                seed=seed,
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
                seed,
                denoise=1.0,
            )

        # Optional second-pass Refine
        if refine is not None and refine.get("enabled", False):
            sampled_latent = apply_refine_pass(
                model=active_model,
                latent_dict=sampled_latent,
                positive=positive,
                negative=negative,
                seed=seed,
                refine_mode=refine.get("mode", "refine"),
                target_width=refine.get("target_width", width),
                target_height=refine.get("target_height", height),
                steps=refine.get("steps", 3),
                denoise=refine.get("denoise", 0.45),
                enable_tiling=refine.get("enable_tiling", False),
                tile_count=refine.get("tile_count", 2),
            )

        # Decode
        decoded_frames = decode_video_latent(video_vae, sampled_latent["samples"].unbind()[0] if hasattr(sampled_latent["samples"], "unbind") else sampled_latent["samples"][0])
        decoded_audio = decode_audio_latent(audio_vae, sampled_latent["samples"].unbind()[-1] if hasattr(sampled_latent["samples"], "unbind") else sampled_latent["samples"][-1]) if audio_vae else {"waveform": torch.zeros((1, 2, 48000)), "sample_rate": 48000}

        # Optional FaceRefine
        if face_refine is not None and face_refine.get("enabled", False):
            decoded_frames, _ = apply_face_refinement(
                decoded_frames=decoded_frames,
                model=active_model,
                vae=video_vae,
                clip=clip,
                seed=seed,
                prompt=face_refine.get("prompt", "cinematic sharp portrait face"),
                strength=face_refine.get("strength", 0.35),
            )

        # Wrap as native video info container if ComfyUI Video support is present
        video_obj = None
        try:
            video_obj = {"images": decoded_frames, "fps": frame_rate, "audio": decoded_audio}
        except Exception:
            pass

        status_str = f"Successfully generated {decoded_frames.shape[0]} frames @ {frame_rate} fps."
        return (
            decoded_frames,
            decoded_audio,
            video_obj,
            positive,
            sampled_latent,
            final_prompt,
            float(frame_rate),
            int(decoded_frames.shape[0]),
            status_str,
        )
