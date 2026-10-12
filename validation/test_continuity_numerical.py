"""CPU tensor checks of the real latent carry implementation, without model weights."""
import unittest
from unittest.mock import patch
import torch
from core.vendor.aimixer.director.h3_latent_continue import apply_latent_continue
from core.vendor.aimixer.director.h3_motion_context import _video_tail_blocks

class ContinuityNumerical(unittest.TestCase):
    def setUp(self):
        self.previous={"samples":(torch.arange(96.).reshape(1,2,12,2,2),torch.full((1,2,2,65),3.))}
        self.target={"samples":(torch.zeros((1,2,22,2,2)),torch.zeros((1,2,2,122)))}

    def test_actual_tail_copy_masks_audio_policy_and_trim(self):
        before=self.previous["samples"][0].clone()
        result,trim,prior_trim=apply_latent_continue(self.target,prev_av=self.previous,prev_tail=None,
            vae=None,context_length=22,audio_context_length=5,pin_audio=True,seam_min_mask=.3)
        blocks,*_= _video_tail_blocks(self.previous,22)
        video,audio=result["samples"]
        self.assertTrue(torch.equal(video[:,:,:7],torch.cat(blocks,dim=2)))
        self.assertTrue(torch.equal(video[:,:,7:],self.target["samples"][0][:,:,7:]))
        self.assertTrue(torch.equal(audio[...,:8],torch.full_like(audio[...,:8],3.)))
        self.assertEqual(torch.count_nonzero(audio[...,8:]).item(),0)
        vm,am=result["noise_mask"]
        self.assertAlmostEqual(vm[0,0,6,0,0].item(),.3,places=6)
        self.assertTrue(torch.all(vm[:,:,7:]==1))
        self.assertTrue(torch.all(am[...,8:]==1))
        self.assertEqual(trim,22)
        self.assertGreaterEqual(prior_trim,0)
        self.assertTrue(torch.equal(self.previous["samples"][0],before))
        self.assertEqual(torch.count_nonzero(self.target["samples"][0]).item(),0)

    def test_audio_off_keeps_target_audio_and_mask_free(self):
        result,trim,_=apply_latent_continue(self.target,prev_av=self.previous,prev_tail=None,
            vae=None,context_length=5,pin_audio=False,audio_context_length=0,seam_min_mask=0)
        self.assertEqual(trim,5)
        self.assertTrue(torch.equal(result["samples"][1],self.target["samples"][1]))
        self.assertTrue(torch.all(result["noise_mask"][1]==1))
        self.assertEqual(result["noise_mask"][0][0,0,1,0,0].item(),0)

    def test_external_pixel_context_encodes_without_trimming_previous_timeline_clip(self):
        class VAE:
            def encode(self,frames):
                self.received=frames
                return torch.ones((1,2,7,2,2))
        vae=VAE();frames=torch.zeros((22,32,32,3))
        with patch('core.vendor.aimixer.director.h3_latent_continue._resize_frames',side_effect=lambda frames,*args:frames):
            result,trim,previous_trim=apply_latent_continue(self.target,prev_av=None,prev_tail=frames,
                vae=vae,context_length=22,pin_audio=False)
        self.assertEqual(vae.received.shape[0],22)
        self.assertTrue(torch.all(result["samples"][0][:,:,:7]==1))
        self.assertEqual((trim,previous_trim),(22,0))

if __name__=='__main__':unittest.main()
