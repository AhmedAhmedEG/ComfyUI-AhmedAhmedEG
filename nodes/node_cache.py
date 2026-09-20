"""Model-scoped MiniMax H3 residual cache node.

Derives speedup by reusing block-stack residuals during diffusion steps.
"""

from __future__ import annotations

import inspect
import logging
import types
from collections.abc import Callable
from typing import Any

import torch

log = logging.getLogger("MiniMaxH3MasterDirector.cache")


class H3BlockStackCache:
    """Reuse the residual emitted by the complete MiniMax H3 block stack."""

    def __init__(
        self,
        reuse_threshold: float,
        start_percent: float,
        end_percent: float,
        max_steps: int,
        device: str,
        verbose: bool,
    ) -> None:
        self.reuse_threshold = reuse_threshold
        self.start_percent = start_percent
        self.end_percent = end_percent
        self.max_steps = max_steps
        self.device = device
        self.verbose = verbose
        self.total_steps = 1
        self.reset()

    def reset(self) -> None:
        self.cached_residual: torch.Tensor | None = None
        self.previous_signature: torch.Tensor | None = None
        self.layout_signature: tuple[Any, ...] | None = None
        self.last_timestep: float | None = None
        self.step = 0
        self.accumulated_relative_l1 = 0.0
        self.consecutive_skips = 0
        self.run_count = 0
        self.skip_count = 0

    def begin(self, total_steps: int) -> None:
        self.reset()
        self.total_steps = max(1, total_steps)

    def finish(self) -> None:
        if self.verbose and self.run_count + self.skip_count:
            total = self.run_count + self.skip_count
            log.info(
                f"MiniMax H3 Cache: skipped {self.skip_count}/{total} block-stack runs "
                f"({total / max(1, self.run_count):.2f}x theoretical speedup)."
            )
        self.reset()

    @staticmethod
    def _signature(hidden_states: torch.Tensor, ranges: tuple[tuple[int, int], ...]) -> torch.Tensor:
        width = min(64, hidden_states.shape[-1])
        samples = []
        for start, end in ranges:
            if end > start:
                stride = max(1, (end - start) // 100)
                samples.append(hidden_states[start:end:stride, :width].detach().abs().mean(dim=-1))
        if not samples:
            stride = max(1, hidden_states.shape[0] // 100)
            return hidden_states[::stride, :width].detach().abs().mean(dim=-1).clone()
        return torch.cat(samples).clone()

    @staticmethod
    def _as_timestep(value: Any) -> float | None:
        if isinstance(value, torch.Tensor):
            return float(value.detach().flatten()[0].item()) if value.numel() else None
        return float(value) if isinstance(value, (int, float)) else None

    def _store_residual(self, residual: torch.Tensor) -> None:
        if self.device == "cuda" and residual.device.type != "cuda":
            raise ValueError("Cache device is cuda but MiniMax H3 is not running on CUDA.")
        try:
            self.cached_residual = (
                residual.detach().to("cpu", copy=True)
                if self.device == "cpu"
                else residual.detach().clone()
            )
        except torch.OutOfMemoryError:
            if self.device == "cuda":
                raise
            self.cached_residual = residual.detach().to("cpu", copy=True)

    def _apply_residual(self, hidden_states: torch.Tensor) -> torch.Tensor:
        residual = self.cached_residual
        if residual is None:
            return hidden_states
        if residual.device != hidden_states.device or residual.dtype != hidden_states.dtype:
            residual = residual.to(hidden_states.device, dtype=hidden_states.dtype, non_blocking=True)
        return hidden_states + residual

    def __call__(self, block_args: dict[str, Any], extra_options: dict[str, Any]) -> dict[str, torch.Tensor]:
        original_block = extra_options["original_block"]
        hidden_states = block_args["img"]
        ranges = tuple(tuple(pair) for pair in block_args.get("cache_ranges", ()))
        layout = (tuple(hidden_states.shape), hidden_states.dtype, hidden_states.device, block_args.get("block_count"), ranges)
        if self.layout_signature != layout:
            total_steps = self.total_steps
            self.reset()
            self.total_steps = total_steps
            self.layout_signature = layout

        timestep = self._as_timestep(block_args.get("timestep"))
        if timestep is None:
            return original_block(block_args)
        if self.last_timestep != timestep:
            self.last_timestep = timestep
            self.step += 1
        progress = self.step / self.total_steps
        in_range = self.start_percent <= progress <= self.end_percent

        if self.cached_residual is not None and self.previous_signature is not None:
            current = self._signature(hidden_states, ranges).float()
            previous = self.previous_signature.float()
            self.accumulated_relative_l1 += (current - previous).abs().mean().item() / (previous.abs().mean().item() + 1e-6)
            if (
                in_range
                and self.accumulated_relative_l1 < self.reuse_threshold
                and self.consecutive_skips < self.max_steps
            ):
                self.skip_count += 1
                self.consecutive_skips += 1
                if self.verbose:
                    log.info(f"MiniMax H3 Cache: step {self.step}: reuse block-stack residual.")
                return {"img": self._apply_residual(hidden_states)}

        self.run_count += 1
        self.consecutive_skips = 0
        self.cached_residual = None
        self.previous_signature = self._signature(hidden_states, ranges)
        before = hidden_states.clone()
        result = original_block(block_args)
        self._store_residual(result["img"] - before)
        self.accumulated_relative_l1 = 0.0
        return result


class H3SamplingScope:
    def __init__(self, cache: H3BlockStackCache) -> None:
        self.cache = cache

    def __call__(self, sample_fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        sigmas = kwargs.get("sigmas")
        if sigmas is None:
            sigmas = next((item for item in args if isinstance(item, torch.Tensor) and item.ndim == 1 and len(item) > 1), None)
        if not isinstance(sigmas, torch.Tensor) or len(sigmas) < 2:
            self.cache.reset()
            raise ValueError("MiniMax H3 Cache could not read the sampler sigma schedule.")
        self.cache.begin(len(sigmas) - 1)
        try:
            return sample_fn(*args, **kwargs)
        finally:
            self.cache.finish()


def final_layer_call(final_layer, hidden_states, timestep_embedding, video_segment, audio_segment,
                     sigma_v, transformer_options, shift_v, shift_a, with_pdd_args):
    if with_pdd_args:
        return final_layer(hidden_states, timestep_embedding, video_segment, audio_segment,
                           sigma_v, transformer_options.get("sample_sigmas"), (shift_v, shift_a))
    return final_layer(hidden_states, timestep_embedding, video_segment, audio_segment)


def build_h3_block_loop_forward(with_pdd_args: bool = False):
    """Build a current-Core _forward equivalent with one block-loop patch boundary."""
    import comfy.ldm.common_dit
    import comfy.model_management
    import comfy.model_prefetch
    from comfy.ldm.minimax import model as minimax_model

    def run_blocks(model, hidden_states, timestep_embedding, mod_segments, rope_freqs, transformer_options):
        replacements = transformer_options.get("patches_replace", {}).get("dit", {})
        queue = comfy.model_prefetch.make_prefetch_queue(list(model.blocks), hidden_states.device, transformer_options)
        for index, block in enumerate(model.blocks):
            comfy.model_prefetch.prefetch_queue_pop(queue, hidden_states.device, block)
            replacement = replacements.get(("double_block", index))
            if replacement is None:
                hidden_states = block(hidden_states, timestep_embedding, mod_segments, rope_freqs, transformer_options=transformer_options)
            else:
                def original(args, block=block):
                    return {"img": block(args["img"], args["t_emb"], args["mod_segments"], args["rope_freqs"], transformer_options=args["transformer_options"])}
                hidden_states = replacement({"img": hidden_states, "t_emb": timestep_embedding, "mod_segments": mod_segments, "rope_freqs": rope_freqs, "transformer_options": transformer_options}, {"original_block": original})["img"]
        if queue is not None:
            comfy.model_prefetch.prefetch_queue_pop(queue, hidden_states.device, None)
        return hidden_states

    def patched_forward(self, x, timestep, context, transformer_options={}, minimax_payload=None, **kwargs):
        video_x, audio_x = x
        orig_t, orig_h, orig_w = video_x.shape[2:5]
        video_x = comfy.ldm.common_dit.pad_to_patch_size(video_x, self.patch_size)
        if video_x.shape[0] != 1:
            raise ValueError("MiniMax H3 supports batch size 1")
        payload, device, dtype = minimax_payload or {}, video_x.device, context.dtype
        latent_t, latent_h, latent_w = video_x.shape[2:5]
        layout = payload.get("layout")
        signature = (context.shape[1], latent_t, latent_h, latent_w, audio_x.shape[-1])
        if layout is None or layout.signature != signature:
            layout = minimax_model.PackedLayout(*signature, keyframes=payload.get("keyframes"), refs=payload.get("refs"))
        shift_v = float(transformer_options.get("minimax_h3_sigma_shift_video", self.sigma_shift_video))
        shift_a = float(transformer_options.get("minimax_h3_sigma_shift_audio", self.sigma_shift_audio))
        sigma_v = (timestep.flatten()[0] / 1000.0).float().clamp(min=1e-6)
        t_v, t_a = float(1.0 - sigma_v), float(1.0 - minimax_model.time_shift_sigma(sigma_v, shift_v, shift_a))
        vis_aug = float(payload.get("visual_cond_noise_aug", minimax_model.VISUAL_COND_TIMESTEP))
        aud_aug = float(payload.get("audio_cond_noise_aug", minimax_model.AUDIO_COND_TIMESTEP))
        segment_t = {"text": t_v, "video": t_v, "audio": t_a, "cond": max(t_v, vis_aug), "ref_img": max(t_v, vis_aug), "cond_audio": max(t_a, aud_aug), "ref_audio": max(t_a, aud_aug)}
        t_pin_v = max(t_v, minimax_model.VISUAL_COND_TIMESTEP)
        t_pin_a = max(t_a, minimax_model.AUDIO_COND_TIMESTEP)
        video_rows_t, audio_rows_t = None, None
        denoise_mask, audio_denoise_mask = kwargs.get("denoise_mask"), kwargs.get("audio_denoise_mask")
        if denoise_mask is not None:
            m = minimax_model.mask_row_values(denoise_mask[0, 0].to(torch.float32), latent_t, latent_h, latent_w)
            if m is not None:
                rows_t = (1.0 - m * sigma_v.to(m.device)).clamp(max=t_pin_v)
                if rows_t.unique().numel() == 1:
                    segment_t["video"] = float(rows_t[0])
                else:
                    video_rows_t = rows_t
        if audio_denoise_mask is not None:
            m = audio_denoise_mask[0, 0].to(torch.float32).reshape(-1)
            if not bool((m >= 1.0 - 1e-3).all()):
                sigma_a = 1.0 - t_a
                rows_t = (1.0 - m * sigma_a).clamp(max=t_pin_a)
                if rows_t.unique().numel() == 1:
                    segment_t["audio"] = float(rows_t[0])
                else:
                    audio_rows_t = rows_t
        unique_t = sorted({t_v, t_a} | {segment_t[kind] for _, _, kind in layout.segments}
                          | (set(video_rows_t.unique().tolist()) if video_rows_t is not None else set())
                          | (set(audio_rows_t.unique().tolist()) if audio_rows_t is not None else set()))
        time_row = {value: index for index, value in enumerate(unique_t)}
        segment_tag = {"text": 1, "video": 0, "audio": 2, "cond": 0, "ref_img": 0, "cond_audio": 2, "ref_audio": 2}

        def rows_to_mod_index(rows_t, tag):
            levels = rows_t.unique()
            base = torch.tensor([time_row[v] * 3 + tag for v in levels.tolist()], dtype=torch.long, device=rows_t.device)
            return base[torch.searchsorted(levels, rows_t)]

        text_tags, mod_segments = payload.get("text_token_tags"), []
        for start, end, kind in layout.segments:
            row_base = time_row[segment_t[kind]] * 3
            if kind == "text" and text_tags is not None:
                tags, run_start = text_tags.view(-1).tolist(), 0
                for index in range(1, end - start + 1):
                    if index == end - start or tags[index] != tags[run_start]:
                        mod_segments.append((start + run_start, start + index, row_base + int(tags[run_start])))
                        run_start = index
            elif kind == "video" and video_rows_t is not None:
                mod_segments.append((start, end, rows_to_mod_index(video_rows_t, segment_tag[kind])))
            elif kind == "audio" and audio_rows_t is not None:
                mod_segments.append((start, end, rows_to_mod_index(audio_rows_t, segment_tag[kind])))
            else:
                mod_segments.append((start, end, row_base + segment_tag[kind]))
        img_update, audio_update = layout.img_update.to(device), layout.audio_update.to(device)
        video_rows = minimax_model.patchify_video(video_x.to(torch.float32), self.patch_size)
        audio_rows = minimax_model.pack_audio(audio_x.to(torch.float32))
        cond_video, cond_audio = self._cond_video_rows(payload, device), self._cond_audio_rows(payload, device)
        if cond_video is not None:
            all_video = torch.empty(img_update.shape[0], video_rows.shape[1], dtype=torch.float32, device=device)
            all_video[~img_update], all_video[img_update] = cond_video, video_rows
        else:
            all_video = video_rows
        if cond_audio is not None:
            all_audio = torch.empty(audio_update.shape[0], audio_rows.shape[1], dtype=torch.float32, device=device)
            all_audio[~audio_update], all_audio[audio_update] = cond_audio, audio_rows
        else:
            all_audio = audio_rows
        video_embed, audio_embed = self.video_patch_proj(all_video).to(dtype), self.audio_patch_proj(all_audio).to(dtype)
        text_states = context[0]
        if text_states.shape[-1] != self.hidden_size:
            text_states = self.token_refiner(self.condition_proj(text_states), transformer_options=transformer_options)
        hidden_states = torch.empty(layout.seq_len, self.hidden_size, dtype=dtype, device=device)
        video_offset = audio_offset = 0
        for start, end, kind in layout.segments:
            length = end - start
            if kind == "text":
                hidden_states[start:end] = text_states
            elif kind in ("cond", "ref_img", "video"):
                hidden_states[start:end] = video_embed[video_offset:video_offset + length]
                video_offset += length
            else:
                hidden_states[start:end] = audio_embed[audio_offset:audio_offset + length]
                audio_offset += length
        times = torch.tensor(unique_t, dtype=torch.float32, device=device)
        if self.use_adaln_curves:
            table = comfy.model_management.cast_to(self.adaln_t_table, device=device)
            position = times.clamp(0.0, 1.0) * (table.shape[0] - 1)
            lower = position.floor().long().clamp(max=table.shape[0] - 2)
            timestep_embedding = torch.lerp(table[lower], table[lower + 1], (position - lower).unsqueeze(1))
        else:
            timestep_embedding = self.time_embedder(times).to(dtype)
        rope_freqs = minimax_model.rope_rotation_table(self.rope_freqs(layout.position_ids, device), dtype)
        replacement = transformer_options.get("patches_replace", {}).get("dit", {}).get(("block_loop", 0))
        if replacement is None:
            hidden_states = run_blocks(self, hidden_states, timestep_embedding, mod_segments, rope_freqs, transformer_options)
        else:
            def original(args):
                return {"img": run_blocks(self, args["img"], args["t_emb"], args["mod_segments"], args["rope_freqs"], args["transformer_options"])}
            cache_ranges = tuple((start, end) for start, end, kind in layout.segments if kind in ("audio", "video"))
            hidden_states = replacement({"img": hidden_states, "timestep": timestep, "t_emb": timestep_embedding, "mod_segments": mod_segments, "rope_freqs": rope_freqs, "transformer_options": transformer_options, "cache_ranges": cache_ranges, "block_count": len(self.blocks)}, {"original_block": original})["img"]
        if video_rows_t is not None:
            video_segment = next((start, end, rows_to_mod_index(video_rows_t, 0) // 3) for start, end, kind in layout.segments if kind == "video")
        else:
            video_segment = next((start, end, time_row[segment_t["video"]]) for start, end, kind in layout.segments if kind == "video")
        if audio_rows_t is not None:
            audio_segment = next((start, end, rows_to_mod_index(audio_rows_t, 0) // 3) for start, end, kind in layout.segments if kind == "audio")
        else:
            audio_segment = next((start, end, time_row[segment_t["audio"]]) for start, end, kind in layout.segments if kind == "audio")
        video_result, audio_result = final_layer_call(self.final_layer, hidden_states, timestep_embedding, video_segment, audio_segment, sigma_v, transformer_options, shift_v, shift_a, with_pdd_args)
        video_out = minimax_model.unpatchify_video(video_result, latent_t, latent_h // 2, latent_w // 2, self.latents_dim, self.patch_size)
        return [-video_out[:, :, :orig_t, :orig_h, :orig_w].to(video_x.dtype), -minimax_model.unpack_audio(audio_result).to(audio_x.dtype)]

    return patched_forward


class MiniMaxH3Cache:
    """Approximate whole-block-stack residual cache for MiniMax H3. Higher thresholds skip more work."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "reuse_threshold": ("FLOAT", {"default": 0.05, "min": 0.0, "max": 1.0, "step": 0.01}),
                "start_percent": ("FLOAT", {"default": 0.15, "min": 0.0, "max": 1.0, "step": 0.01}),
                "end_percent": ("FLOAT", {"default": 0.90, "min": 0.0, "max": 1.0, "step": 0.01}),
                "max_steps": ("INT", {"default": 2, "min": 1, "max": 10}),
                "device": (["auto", "cuda", "cpu"], {"default": "auto"}),
                "verbose": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "patch"
    CATEGORY = "ComfyUI-AhmedAhmedEG"
    DESCRIPTION = "Optional approximate DiT residual cache for MiniMax H3 (1.5x-2x speedup). WARNING: Prone to ghosting, motion blur, and temporal smearing on dynamic scenes. Keep disconnected/disabled for maximum visual fidelity."

    def patch(self, model, reuse_threshold, start_percent, end_percent, max_steps, device, verbose):
        if start_percent > end_percent:
            raise ValueError("start_percent must not exceed end_percent.")
        patched = model.clone()
        diffusion_model = patched.model.diffusion_model
        if diffusion_model.__class__.__name__ != "MiniMaxH3Model" or not hasattr(diffusion_model, "blocks"):
            raise ValueError("MiniMax H3 Cache requires a MiniMax H3 diffusion model.")
        cache = H3BlockStackCache(reuse_threshold, start_percent, end_percent, max_steps, device, verbose)
        final_layer_params = inspect.signature(diffusion_model.final_layer.forward).parameters
        with_pdd_args = "sample_sigmas" in final_layer_params
        patched.add_object_patch("diffusion_model._forward", types.MethodType(build_h3_block_loop_forward(with_pdd_args), diffusion_model))
        patched.set_model_patch_replace(cache, "dit", "block_loop", 0)
        try:
            import comfy.patcher_extension
            wrapper_type = comfy.patcher_extension.WrappersMP.OUTER_SAMPLE
        except ImportError:
            wrapper_type = "outer_sample"
        patched.add_wrapper(wrapper_type, H3SamplingScope(cache))
        return (patched,)
