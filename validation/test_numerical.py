"""Run separately with CPU PyTorch; no fake tensor runtime or model weights."""
import math
import sys
import types
import unittest
from types import SimpleNamespace
import torch

utils = types.ModuleType("comfy.utils")
def pack(parts):
    return torch.cat([part.reshape(part.shape[0], 1, -1) for part in parts], dim=-1), [part.shape for part in parts]
def unpack(value, shapes):
    sizes = [math.prod(shape[1:]) for shape in shapes]
    return [part.reshape(shape) for part, shape in zip(value.split(sizes, dim=-1), shapes)]
utils.pack_latents, utils.unpack_latents = pack, unpack
comfy = types.ModuleType("comfy"); comfy.utils = utils
sys.modules["comfy"] = comfy; sys.modules["comfy.utils"] = utils

from core.vendor.aimixer.director.spatial_tiled_sampling import wrap_sampler_spatial_tiles
from core.vendor.aimixer.director.selflift.sample import _euler_step
from core.vendor.aimixer.director.h3_latent_upscale import LatentResizer3D
from core.output_processing import playback, seamless_loop, watermark
from core.references import waveform


class Numerical(unittest.TestCase):
    def test_tracked_face_follows_boxes_and_keeps_crop_inside_source(self):
        from unittest.mock import patch
        from core.vendor.aimixer.director.face_refine.track import track_and_crop
        class Boxes:
            def __init__(self,x): self.xyxy=torch.tensor([[x,10,x+20,30.]])
            def __len__(self):return 1
        class Detector:
            index=0
            def predict(self,*args,**kwargs):
                self.index+=1
                return [SimpleNamespace(boxes=Boxes(8+self.index*3))]
        frames=torch.rand((5,64,96,3));original=frames.clone()
        with patch('core.vendor.aimixer.director.face_refine.track.load_detector',return_value=Detector()):
            crops,transform,report=track_and_crop(frames,{'canvas_width':32,'canvas_height':32,'crop_factor':1.5})
        self.assertEqual(crops.shape,(5,32,32,3))
        self.assertGreater(transform['boxes'][-1][0],transform['boxes'][0][0])
        for x,y,width,height in transform['boxes']:
            self.assertGreaterEqual(min(x,y),0)
            self.assertLessEqual(x+width,96);self.assertLessEqual(y+height,64)
        self.assertTrue(torch.equal(frames,original))

    def test_tracked_face_reports_no_detections_without_fabricated_crop(self):
        from unittest.mock import patch
        from core.vendor.aimixer.director.face_refine.track import track_and_crop
        detector=SimpleNamespace(predict=lambda *args,**kw:[SimpleNamespace(boxes=[])])
        frames=torch.rand((5,32,32,3))
        with patch('core.vendor.aimixer.director.face_refine.track.load_detector',return_value=detector):
            crops,transform,report=track_and_crop(frames,{})
        self.assertIsNone(crops);self.assertIsNone(transform)
        self.assertIn('skipped',report)

    def test_face_stitch_zero_blend_is_identity_without_mutating_frames(self):
        from core.vendor.aimixer.director.face_refine.stitch import stitch_faces
        source = torch.rand((3,32,32,3)); original = source.clone()
        crops = torch.ones((3,16,16,3))
        result = stitch_faces(source,crops,{"boxes":[(4,4,16,16)]*3},
            {"blend":0,"colour_match":0,"feather":0,"mask_dilation":0})
        self.assertTrue(torch.equal(result,original))
        self.assertTrue(torch.equal(source,original))

    def test_continuation_refine_keeps_old_prefix_and_repins_full_native_guide(self):
        from core.vendor.dasiwa.nodes_minimax_h3_tiled_upscale import continuity_refine_mask
        from core.vendor.dasiwa.h3_upscale_continuity import align_continuity_conditioning
        video = torch.rand((1,24,12,4,4)); audio = torch.rand((1,32,2,50))
        plan = {"refine_start_token":6,"guide_start_token":0,"source_tokens":7,
            "frame_offset":0,"audio_start":0,"source_audio_tokens":23}
        mask = continuity_refine_mask(video,0,plan,soft=True)
        self.assertEqual(float(mask[:,:,:6].sum()),0)
        self.assertEqual(float(mask[:,:,7:].min()),1)
        conditioning = [[torch.ones((1,2,3)),{}]]
        result = align_continuity_conditioning(conditioning,video,audio,plan)
        guide = result[0][1]["minimax_keyframes"][0]
        self.assertEqual(guide["latent"].shape[2],7)
        self.assertEqual(guide["audio_latent"].shape[-1],23)
        self.assertEqual(conditioning[0][1],{})

    def test_tiled_forward_uses_one_trajectory_and_restores_shapes(self):
        video = torch.rand((1, 24, 2, 4, 120))
        audio = torch.rand((1, 32, 2, 12))
        value, shapes = pack([video, audio])
        base = SimpleNamespace(latent_shapes=shapes)
        class Model:
            inner_model = SimpleNamespace(inner_model=base, conds={})
            latent_image = None
            noise = None
            calls = 0
            def __call__(self, x, sigma, denoise_mask=None, **kwargs):
                self.calls += 1
                return x + .125
        calls = []
        def sampler_function(model, noise, sigmas, **kwargs):
            calls.append("trajectory")
            for sigma in sigmas[:-1]: noise = model(noise, sigma)
            return noise
        sampler = SimpleNamespace(sampler_function=sampler_function)
        restore = wrap_sampler_spatial_tiles(sampler, n_tiles=3, overlap_pixels=128)
        model = Model()
        result = sampler.sampler_function(model, value, torch.tensor([1., .5, 0.]))
        restore()
        self.assertTrue(torch.allclose(result, value + .25, atol=1e-6))
        self.assertEqual(calls, ["trajectory"])
        self.assertEqual(model.calls, 6)
        self.assertIs(base.latent_shapes, shapes)
        self.assertIs(sampler.sampler_function, sampler_function)

    def test_euler_state_transition_is_not_a_clean_latent_resume(self):
        state, denoised = torch.tensor([2.]), torch.tensor([.5])
        self.assertTrue(torch.equal(_euler_step(state, denoised, 1., .5), torch.tensor([1.25])))

    def test_checkpoint_architecture_rejects_incomplete_and_detects_temporal_indices(self):
        from core.vendor.dasiwa.h3_latent_upscale import _LatentResizer3D, _validated_state_dict
        network = _LatentResizer3D(in_channels=24,in_blocks=2,out_blocks=2,channels=32,temporal_every=1,temporal_kernel=3)
        sd, configuration = _validated_state_dict(network.state_dict())
        restored = _LatentResizer3D(**configuration)
        restored.load_state_dict(sd,strict=True)
        broken = dict(sd); broken.pop("conv_in.weight")
        with self.assertRaises(ValueError): _validated_state_dict(broken)

    def test_nested_masks_and_low_carry_are_safe_to_reload(self):
        import tempfile
        from pathlib import Path
        from core.cache_manager import portable_tree
        class Nested:
            is_nested = True
            def unbind(self): return (torch.zeros((1,24,2,2,2)),torch.zeros((1,32,2,8)))
        value = {"samples":Nested(),"noise_mask":Nested(),"_selflift_low_carry":{"samples":Nested()}}
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/"latent.pt"; torch.save(portable_tree(value),path)
            restored = torch.load(path,weights_only=True)
            self.assertEqual(len(restored["_selflift_low_carry"]["samples"]["_mmx_nested"]),2)

    def test_learned_upscale_preserves_time_and_channels(self):
        network = LatentResizer3D(in_channels=24, in_blocks=1, out_blocks=1, channels=32, dropout=0., temporal_every=1, temporal_kernel=3).eval()
        with torch.inference_mode(): result = network(torch.rand((1,24,3,4,4)), 2., (3,8,8))
        self.assertEqual(result.shape, (1,24,3,8,8))
        self.assertTrue(torch.isfinite(result).all())

    def test_loop_and_playback_keep_audio_duration_synchronized(self):
        frames = torch.rand((48,8,8,3))
        audio = {"waveform": torch.rand((1,2,96000)), "sample_rate":48000}
        images, sound = playback(frames, audio, 24., 30., "resample")
        self.assertEqual(images.shape[0], 60)
        self.assertEqual(sound["waveform"].shape[-1], 96000)
        images, sound = seamless_loop(images, sound, 30., 6)
        self.assertEqual(images.shape[0], 54)
        self.assertEqual(sound["waveform"].shape[-1], 86400)

    def test_logo_does_not_mutate_frames_and_waveform_uses_decoded_samples(self):
        frames = torch.zeros((2,8,8,3)); logo = torch.ones((1,2,2,4))
        result = watermark(frames, logo=logo, opacity=.5, margin=0)
        self.assertEqual(float(frames.sum()), 0.)
        self.assertEqual(float(result[:, -2:, -2:].mean()), .5)
        audio = {"waveform": torch.tensor([[[0., 1., 0., .5]]])}
        self.assertEqual(waveform(audio, 8), [0., 1., 0., .5])


if __name__ == "__main__": unittest.main()
