"""Regression tests for native API contracts and execution/cache behavior."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from tests.mock_torch import setup_mock_torch_if_needed
torch = setup_mock_torch_if_needed()
from core.sampling import sample_latent, native_outputs
from core.cache_manager import ProjectCacheManager, fingerprint_value
from core.media_io import resolve_input_path
from core.audio_post import fit_audio_duration
from nodes.node_director import MiniMaxH3MasterDirector
from nodes.node_ref_pack import MiniMaxH3RefPack
from nodes.node_groups import MiniMaxH3DirectorGroupImageToVideo
from core.config import align_frame_count, video_latent_t, audio_latent_length


class NativeOutput:
    def __init__(self, *result):
        self.result = result


class SmallVAE:
    def encode(self, pixels):
        return torch.zeros((1, 24, video_latent_t(pixels.shape[0]), 2, 2))

    def decode(self, latent):
        if latent.ndim == 5:
            frames = 5 if latent.shape[2] <= 2 else (latent.shape[2] - 2) // 5 * 17 + 5
            return torch.zeros((frames, 32, 32, 3))
        return torch.zeros((1, latent.shape[-1] * 800, 2))


class RuntimeContracts(unittest.TestCase):
    def test_model_override_pack_does_not_request_unconnected_family_models(self):
        self.assertEqual(MiniMaxH3MasterDirector.check_lazy_status(
            model_pack={"custom":object()},timeline_data=json.dumps({"clips":[{"type":"T2VA","model_override":"custom"}]})),[])
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.node = MiniMaxH3MasterDirector()
        self.vae = SmallVAE()
        self.audio_vae = SmallVAE()
        self.audio_vae.audio_sample_rate = 32000
        self.clip = SimpleNamespace()
        self.model = SimpleNamespace(model_name="test-h3")
        self.native_calls = []
        self.sampling_calls = []
        self.patches = [
            patch("core.cache_manager.get_cache_root_dir", return_value=self.temp.name),
            patch("core.executor.get_native_h3_node", side_effect=self.native),
            patch("comfy.sample.fix_empty_latent_channels", side_effect=lambda m, s, *a: s),
            patch("comfy.sample.prepare_noise", side_effect=lambda s, seed, batch=None: s),
            patch("comfy.sample.prepare_empty_noise", side_effect=lambda s: s),
            patch("comfy.sample.sample", side_effect=self.strict_sample),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def strict_sample(self, model, noise, steps, cfg, sampler_name, scheduler,
                      positive, negative, latent_image, denoise=1., disable_noise=False,
                      start_step=None, last_step=None, force_full_denoise=False,
                      noise_mask=None, sigmas=None, callback=None, seed=None):
        self.assertNotIsInstance(noise, dict)
        self.assertNotIsInstance(latent_image, dict)
        self.sampling_calls.append({"model": model, "seed": seed, "steps": steps,
            "samples": latent_image, "sigmas": sigmas, "noise_mask": noise_mask,
            "disable_noise": disable_noise, "start_step": start_step, "last_step": last_step})
        return latent_image

    def native(self, name):
        owner = self
        class Native:
            @classmethod
            def execute(cls, **kw):
                owner.native_calls.append((name, kw))
                if name == "MiniMaxH3AddGuide":
                    positive = [[emb, {**meta, "guide_used": True}] for emb, meta in kw["positive"]]
                    return NativeOutput(positive)
                frames = align_frame_count(kw["length"])
                samples = (torch.zeros((1, 24, video_latent_t(frames), 2, 2)),
                           torch.zeros((1, 32, 2, audio_latent_length(frames))))
                return NativeOutput([[torch.zeros((1, 2, 5120)), {}]], {"samples": samples})
        return Native

    def execute(self, clips=None, **kwargs):
        options = {"model": self.model, "video_vae": self.vae, "audio_vae": self.audio_vae,
            "clip": self.clip, "config": {"project_id": "regression", "run_mode": "full_batch"},
            "timeline_data": json.dumps({"clips": clips or [{"id": "one", "type": "T2VA", "duration": 1., "prompt": "walk"}]})}
        options.update(kwargs)
        return self.node.execute(**options)

    def test_hidden_execution_graph_is_not_used_as_prompt(self):
        result = self.execute(
            [{"id": "one", "type": "T2VA", "duration": 1., "prompt": ""}],
            config={"project_id": "regression", "run_mode": "full_batch", "prompt": "walk"},
            prompt={"private_graph_marker": {"class_type": "MiniMaxH3MasterNode"}},
        )
        self.assertEqual(result[5], "walk")

    def test_sampler_tensor_contract_and_metadata(self):
        tensor = torch.zeros((1, 24, 2, 2, 2))
        mask = torch.ones((1, 1, 2, 2, 2))
        sigmas = torch.linspace(1, 0, 4)
        output = sample_latent(self.model, {"samples": tensor, "noise_mask": mask, "batch_index": [0]},
            3, 1, "euler", "simple", [], [], 42, sigmas=sigmas)
        self.assertIs(output["samples"], tensor)
        self.assertIs(output["noise_mask"], mask)
        self.assertIs(self.sampling_calls[0]["sigmas"], sigmas)
        self.assertEqual(self.sampling_calls[0]["seed"], 42)

    def test_native_node_output_unwrapping(self):
        self.assertEqual(native_outputs(NativeOutput(1, 2)), (1, 2))
        self.assertEqual(native_outputs((1, 2)), (1, 2))

    def test_all_canonical_modes_route_to_correct_native_family(self):
        for mode in ("T2VA", "I2VA", "FL2VA", "L2VA", "REF2VA", "V2V", "RV2V"):
            self.native_calls.clear()
            self.execute([{ "id": "one", "type": mode, "duration": 1}], execution_mode="Conditioning Guide Output")
            expected = "MiniMaxH3ImageToVideo" if mode in ("T2VA", "I2VA", "FL2VA", "L2VA") else "MiniMaxH3ReferenceToVideo"
            self.assertEqual(self.native_calls[0][0], expected)

    def test_generic_model_never_uses_wrong_family_socket(self):
        wrong_model = SimpleNamespace(model_name="wrong-family")
        self.execute(ref2va_model=wrong_model)
        self.assertIs(self.sampling_calls[0]["model"], self.model)

    def test_lazy_guide_mode_needs_no_model(self):
        self.assertEqual(self.node.check_lazy_status(config={"execution_mode": "Conditioning Guide Output"}), [])
        self.assertEqual(self.node.check_lazy_status(timeline_data=json.dumps({"clips": [{"type": "RV2V"}]})), ["ref2va_model"])

    def test_returned_latent_is_sampled_and_audio_matches_video(self):
        result = self.execute()
        self.assertIs(result[4]["samples"], self.sampling_calls[0]["samples"])
        self.assertEqual(result[1]["waveform"].shape[-1], round(result[7] / result[6] * 48000))
        self.assertEqual(result[2]["loaded_frame_count"], result[7])

    def test_cache_reuse_after_user_validates_and_settings_invalidate(self):
        clips = [{"id": "one", "type": "T2VA", "duration": 1, "prompt": "walk"}]
        self.execute(clips)
        clips[0]["validated"] = True
        self.sampling_calls.clear()
        self.execute(clips)
        self.assertEqual(self.sampling_calls, [])
        self.execute(clips, steps=26)
        self.assertEqual(len(self.sampling_calls), 1)

    def test_reference_contents_invalidate_cache(self):
        clips = [{"id": "one", "type": "REF2VA", "duration": 1, "validated": True, "ref_ids": ["image_1"]}]
        self.execute(clips, ref_pack=MiniMaxH3RefPack().pack(image_1=torch.zeros((1, 32, 32, 3)))[0])
        self.sampling_calls.clear()
        self.execute(clips, ref_pack=MiniMaxH3RefPack().pack(image_1=torch.ones((1, 32, 32, 3)))[0])
        self.assertEqual(len(self.sampling_calls), 1)

    def test_upstream_change_invalidates_chained_cache(self):
        clips = [{"id": "one", "type": "T2VA", "duration": 1, "seed": 1, "validated": True},
                 {"id": "two", "type": "T2VA", "duration": 1, "seed": 2, "validated": True}]
        self.execute(clips)
        self.sampling_calls.clear()
        self.execute(clips)
        self.assertEqual(len(self.sampling_calls), 0)
        clips[0]["seed"] = 3
        self.execute(clips)
        self.assertEqual([x["seed"] for x in self.sampling_calls], [3, 2])

    def test_independent_mode_does_not_invalidate_later_clip(self):
        clips = [{"id": "one", "type": "T2VA", "duration": 1, "seed": 1, "validated": True},
                 {"id": "two", "type": "T2VA", "duration": 1, "seed": 2, "validated": True}]
        self.execute(clips, continuity_mode="Independent (No Continuity)")
        self.sampling_calls.clear()
        clips[0]["seed"] = 3
        self.execute(clips, continuity_mode="Independent (No Continuity)")
        self.assertEqual([x["seed"] for x in self.sampling_calls], [3])

    def test_clip_by_clip_stops_after_one_new_shot(self):
        clips = [{"id": str(i), "type": "T2VA", "duration": 1} for i in range(3)]
        result = self.execute(clips, run_mode="clip_by_clip")
        self.assertEqual(len(self.sampling_calls), 1)
        self.assertEqual(result[7], 39)

    def test_native_text_and_groups_are_consumed(self):
        group, = MiniMaxH3DirectorGroupImageToVideo().pack(prompt="group prompt", duration_sec=1.)
        result = self.execute(i2v_groups=group, prompt_text="\nbridge prompt\n\n")
        self.assertEqual(result[5], "bridge prompt")

    def test_reference_group_size_reaches_native_conditioning(self):
        from nodes.node_groups import MiniMaxH3DirectorGroupReferenceToVideo
        group, = MiniMaxH3DirectorGroupReferenceToVideo().pack(
            prompt="A person turns", duration_sec=1., ref_image_size="1536",
            ref_image_1=torch.zeros((1, 32, 32, 3)))
        result = self.execute(r2v_groups=group, timeline_data="{}", continuity_mode="Independent (No Continuity)")
        native = next(kw for name, kw in self.native_calls if name == "MiniMaxH3ReferenceToVideo")
        self.assertEqual(native["ref_image_size"], "1536")
        self.assertNotIn("group", json.loads(result[9])["clips"][0])
        saved = json.loads((__import__("pathlib").Path(self.temp.name)/"regression"/"autosave.json").read_text())
        self.assertNotIn("group", saved["clips"][0])
        self.assertIsNotNone(group["ref_images"]["ref_image_1"])

    def test_original_canvas_uses_real_reference_pool_tensor_size(self):
        from core.resolution import timeline_media_size
        pack, = MiniMaxH3RefPack().pack(image_1=torch.zeros((1, 128, 256, 3)))
        with patch.dict(__import__("sys").modules, {"folder_paths": SimpleNamespace(get_input_directory=lambda: self.temp.name)}):
            self.assertEqual(timeline_media_size({}, pack), (256, 128))

    def test_fallback_reference_aliases_are_deduplicated(self):
        pack, = MiniMaxH3RefPack().pack(image_1=torch.zeros((1, 32, 32, 3)))
        self.execute(ref_pack=pack, timeline_data="{}", execution_mode="Conditioning Guide Output")
        self.assertEqual(len(self.native_calls[0][1]["ref_images"]), 1)

    def test_reference_motion_context_uses_native_guide(self):
        clips = [{"id": "one", "type": "T2VA", "duration": 1},
                 {"id": "two", "type": "REF2VA", "duration": 1}]
        result = self.execute(clips)
        guides = [kw for name, kw in self.native_calls if name == "MiniMaxH3AddGuide"]
        self.assertEqual(len(guides), 1)
        self.assertEqual(guides[0]["frame_idx"], 0)
        self.assertEqual(guides[0]["image"].shape[0], 22)
        self.assertEqual(result[7], 39 + 39)

    def test_per_shot_context_overrides_global_and_can_disable_audio(self):
        clips = [{"id":"one","type":"T2VA","duration":2,"continuity_mode":"Independent (No Continuity)"},
                 {"id":"two","type":"T2VA","duration":2,"continuity_mode":"Motion Context (Chained)","context_length":39,"audio_context_length":0}]
        self.execute(clips, continuity_mode="Independent (No Continuity)")
        guides = [kw for name,kw in self.native_calls if name=="MiniMaxH3AddGuide"]
        self.assertEqual(guides[0]["image"].shape[0],39)
        self.assertIsNone(guides[0].get("audio"))

    def test_master_timeline_generation_mode_overrides_config(self):
        clips=[{"id":"one","type":"T2VA","duration":1},{"id":"two","type":"T2VA","duration":1}]
        self.execute(timeline_data=json.dumps({"version":2,"project_id":"regression","generation_mode":"Next shot","clips":clips}),run_mode="full_batch")
        self.assertEqual(len(self.sampling_calls),1)

    def test_continuity_modes_validate_and_clamp_audio(self):
        from core.continuity import resolve_continuity
        result=resolve_continuity({"continuity_mode":"Latent Carry (Pinned)","context_length":5,"audio_context_length":56})
        self.assertEqual(result["audio_frames"],5)
        self.assertEqual(resolve_continuity({"continuity_mode":"FL2VA Tail Handoff"})["video_frames"],1)
        self.assertEqual(resolve_continuity({"continuity":False})["video_frames"],0)
        with self.assertRaises(ValueError):resolve_continuity({"context_length":12})

    def test_latent_carry_receives_per_shot_audio_policy(self):
        clips=[{"id":"one","type":"T2VA","duration":2,"continuity_mode":"Independent (No Continuity)"},
               {"id":"two","type":"T2VA","duration":2,"continuity_mode":"Latent Carry (Pinned)","context_length":39,"audio_context_length":5,"continuity_redraw":.3}]
        with patch('core.vendor.aimixer.director.h3_latent_continue.apply_latent_continue',side_effect=lambda latent,**kw:(latent,39,0)) as carry, patch('core.advanced_sampling.sample_stage',side_effect=lambda model,latent,*args,**kw:latent):
            self.execute(clips)
        self.assertEqual(carry.call_args.kwargs['context_length'],39)
        self.assertEqual(carry.call_args.kwargs['audio_context_length'],5)
        self.assertTrue(carry.call_args.kwargs['pin_audio'])
        self.assertEqual(carry.call_args.kwargs['seam_min_mask'],.3)

    def test_clip_by_clip_advances_only_the_completed_seed(self):
        clips = [{"id":"one","type":"T2V","duration":1,"seed":"18446744073709551615","seed_mode":"increment"},
                 {"id":"two","type":"T2V","duration":1,"seed":"42","seed_mode":"increment"}]
        result = self.execute(clips,run_mode="clip_by_clip")
        with open(os.path.join(self.temp.name,"regression","autosave.json"),encoding="utf-8") as stream:
            state = json.load(stream)
        self.assertEqual(state["clips"][0]["seed"],"0")
        self.assertEqual(state["clips"][0]["last_seed"],"18446744073709551615")
        self.assertEqual(state["clips"][1]["seed"],"42")
        self.assertNotIn("last_seed",state["clips"][1])
        self.assertEqual(result[1]["waveform"].shape[-1], round(result[7] / 24 * 48000))
        project = json.loads(result[9])
        self.assertEqual(project["project_id"],"regression")
        self.assertEqual(project["clips"][0]["last_seed"],"18446744073709551615")


    def test_tiles_cover_small_canvas_with_excessive_tile_count(self):
        from core.vendor.aimixer.director.spatial_tiled_sampling import compute_tile_starts
        starts, width = compute_tile_starts(4, 8, 32)
        covered = set()
        for start in starts:
            covered.update(range(start, min(4, start + width)))
        self.assertEqual(covered, set(range(4)))

    def test_inpaint_requires_one_image_and_non_native_fps_fail_clearly(self):
        with self.assertRaisesRegex(ValueError, "24 fps"):
            self.execute(frame_rate=30)
        with self.assertRaisesRegex(ValueError, "exactly one image"):
            self.execute([{ "id": "one", "type": "Image Inpaint", "duration": 1}])

    def test_upstream_image_inpaint_workflow_returns_one_generated_still(self):
        pack, = MiniMaxH3RefPack().pack(image_1=torch.zeros((1, 32, 32, 3)))
        result = self.execute([{ "id": "one", "type": "Image Inpaint", "duration": 8,
            "ref_ids": ["image_1"]}], ref_pack=pack)
        self.assertEqual(self.native_calls[0][1]["length"], 5)
        self.assertIsNotNone(self.native_calls[0][1]["first_frame"])
        self.assertEqual(result[7], 1)

    def test_lora_rows_validate_strength_and_enabled_flags(self):
        from core.loras import normalize_loras, resolve_lora_files
        self.assertEqual(resolve_lora_files([{"name": "disabled", "enabled": False}]), [])
        self.assertEqual(normalize_loras([{"name": "a", "strength": .5}]), [{"name": "a", "strength": .5}])
        with self.assertRaises(ValueError):
            normalize_loras([{"name": "a", "strength": float("nan")}])

    def test_lora_file_changes_change_content_signature(self):
        import sys
        from core.loras import resolve_lora_files
        path = os.path.join(self.temp.name, "weights.safetensors")
        folder_paths = SimpleNamespace(get_full_path_or_raise=lambda category, name: path)
        with patch.dict(sys.modules, {"folder_paths": folder_paths}):
            with open(path, "wb") as f: f.write(b"first")
            first = resolve_lora_files([{"name": "test"}])
            with open(path, "wb") as f: f.write(b"second")
            second = resolve_lora_files([{"name": "test"}])
        self.assertNotEqual(first[0]["sha256"], second[0]["sha256"])

    def test_shot_lora_does_not_leak_into_the_next_shot(self):
        import sys, types, comfy
        class Model(SimpleNamespace):
            def clone(self):
                return Model(model_name=self.model_name, patches=list(self.patches))
        base = Model(model_name="test-h3", patches=[])
        weights_path = os.path.join(self.temp.name, "weights.safetensors")
        with open(weights_path, "wb") as stream:
            stream.write(b"test checkpoint")
        paths = SimpleNamespace(get_full_path_or_raise=lambda category, name: weights_path)
        sd, utils = types.ModuleType("comfy.sd"), types.ModuleType("comfy.utils")
        def load(model, clip, state, strength_model, strength_clip):
            model.patches.append(strength_model)
            return model, clip
        sd.load_lora_for_models = load
        utils.load_torch_file = lambda path, safe_load: {"weights": "fixture"}
        with patch.dict(sys.modules, {"folder_paths": paths, "comfy.sd": sd, "comfy.utils": utils}), \
             patch.object(comfy, "sd", sd), patch.object(comfy, "utils", utils):
            self.execute([{ "id": "one", "type": "T2VA", "duration": 1,
                "loras": [{"name": "test", "strength": .7}]},
                {"id": "two", "type": "T2VA", "duration": 1}], model=base)
        self.assertEqual(self.sampling_calls[0]["model"].patches, [.7])
        self.assertEqual(self.sampling_calls[1]["model"].patches, [])
        self.assertEqual(base.patches, [])

    def test_source_edit_binds_video_one_and_keeps_original_audio(self):
        source = {"frames": torch.ones((17, 32, 32, 3)),
            "audio": {"waveform": torch.ones((1, 2, 32000)), "sample_rate": 32000}}
        with patch("nodes.node_director.source_range", return_value=source):
            result = self.execute([{ "id": "edit", "type": "RV2V", "duration": 1,
                "audio_mode": "source"}])
        self.assertIs(self.native_calls[0][1]["ref_videos"]["ref_video_1"], source["frames"])
        self.assertEqual(result[7], 17)
        self.assertEqual(result[1]["waveform"].shape[-1], 34000)

    def test_unselected_source_shot_passes_through_without_sampling(self):
        source = {"frames": torch.ones((17, 32, 32, 3)),
            "audio": {"waveform": torch.ones((1, 2, 32000)), "sample_rate": 32000}}
        with patch("nodes.node_director.source_range", return_value=source):
            result = self.execute(timeline_data=json.dumps({"run_selection": True,
                "clips": [{"id": "skip", "type": "V2V", "duration": 1, "selected": False}]}))
        self.assertEqual(self.sampling_calls, [])
        self.assertEqual(result[7], 17)
        self.assertTrue(bool((result[0] == 1).all()))


    def test_source_mute_policy_has_exact_visible_duration(self):
        from core.source_media import choose_audio
        audio = choose_audio("mute", {}, None, 17)
        self.assertEqual(audio["waveform"].shape[-1], 34000)
        self.assertTrue(bool((audio["waveform"] == 0).all()))

    def test_cache_paths_cannot_escape_project(self):
        for name in ("..", "../escape", "C:\\escape", "CON", "name."):
            with self.assertRaises(ValueError):
                ProjectCacheManager(name, self.temp.name)
        manager = ProjectCacheManager("safe", self.temp.name)
        with self.assertRaises(ValueError):
            manager.get_clip_latent_path("../../escape")

    def test_absolute_input_path_must_obey_supplied_root(self):
        path = os.path.join(self.temp.name, "outside.txt")
        with open(path, "w") as f:
            f.write("x")
        root = os.path.join(self.temp.name, "input")
        os.mkdir(root)
        with self.assertRaises(ValueError):
            resolve_input_path(path, root)

    def test_import_cannot_assign_fingerprint_to_existing_cache(self):
        manager = ProjectCacheManager("safe", self.temp.name)
        from core.config import PROJECT_FORMAT, PROJECT_FORMAT_VERSION
        project = {"format": PROJECT_FORMAT, "version": PROJECT_FORMAT_VERSION, "timeline": {"clips": []},
            "server_cache_manifest": {"one": {"fingerprint": "forged", "validated": True}}}
        manager.import_lightweight_project_data(project)
        self.assertEqual(manager._manifest["clips"], {})

    def test_media_hash_depends_on_contents_and_order(self):
        zero, one = torch.zeros((1, 2)), torch.ones((1, 2))
        self.assertNotEqual(fingerprint_value([zero, one]), fingerprint_value([one, zero]))
        self.assertEqual(fingerprint_value(zero), fingerprint_value(zero.clone()))

    def test_audio_duration_padding_and_trimming(self):
        audio = {"waveform": torch.zeros((1, 2, 5)), "sample_rate": 48000}
        self.assertEqual(fit_audio_duration(audio, 24)["waveform"].shape[-1], 48000)

    def test_invalid_json_and_duplicate_ids_do_not_generate(self):
        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            self.execute(timeline_data="broken")
        with self.assertRaisesRegex(ValueError, "unique"):
            self.execute([{ "id": "same", "type": "T2VA"}, {"id": "same", "type": "T2VA"}])
        self.assertEqual(self.sampling_calls, [])

    def test_deleted_last_shot_does_not_generate_a_fallback(self):
        with self.assertRaisesRegex(ValueError, "no shots.*Add Shot"):
            self.execute(timeline_data=json.dumps({"clips": []}))
        self.assertEqual(self.sampling_calls, [])

    def test_invalid_sigmas_do_not_reach_sampler(self):
        with self.assertRaisesRegex(ValueError, "SIGMAS"):
            self.execute(sigmas=torch.tensor([0., 1., 0.]))
        self.assertEqual(self.sampling_calls, [])

    def test_refmod_audio_reports_actual_token_length(self):
        from core.executor import MasterDirectorExecutor
        class Clip:
            def tokenize(self, text, **kwargs): return kwargs
            def encode_from_tokens_scheduled(self, tokens): return [[torch.zeros((1, 2, 5120)), {}]]
        positive, _, _ = MasterDirectorExecutor().build_conditioning(
            mode="REF2VA", prompt="sound", width=32, height=32, duration=1,
            clip=Clip(), vae=self.vae, audio_vae=self.audio_vae,
            refmod_items=[{"kind": "audio", "latent": torch.zeros((1, 32, 2, 17))}])
        self.assertEqual(positive[0][1]["minimax_refs"][0]["ref_audio_t"], 17)

    def test_multiple_cache_managers_preserve_manifest_entries(self):
        a, b = ProjectCacheManager("shared", self.temp.name), ProjectCacheManager("shared", self.temp.name)
        latent = {"samples": (torch.zeros((1, 24, 2, 2, 2)), torch.zeros((1, 32, 2, 8)))}
        a.store_clip_results("one", "a", latent)
        b.store_clip_results("two", "b", latent)
        self.assertTrue(a.is_clip_cached_and_valid("one", "a"))
        self.assertTrue(a.is_clip_cached_and_valid("two", "b"))

    def test_ffmpeg_failure_is_not_reported_as_success(self):
        import io
        from nodes.node_video_combine import MiniMaxH3VideoCombine
        process = SimpleNamespace(stdin=io.BytesIO(), returncode=1, wait=lambda: 1)
        with patch("nodes.node_video_combine.FFMPEG_PATH", "ffmpeg"), \
             patch("nodes.node_video_combine.resolve_output_path", return_value=(os.path.join(self.temp.name, "bad.mp4"), "bad.mp4", "")), \
             patch("nodes.node_video_combine.subprocess.Popen", return_value=process):
            with self.assertRaisesRegex(RuntimeError, "ffmpeg failed"):
                MiniMaxH3VideoCombine().combine_video(torch.zeros((5, 32, 32, 3)), encoder_backend="ffmpeg")



if __name__ == "__main__":
    unittest.main()
