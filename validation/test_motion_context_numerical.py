"""Real CPU tensor contracts for temporal guides and long-chain audio accounting."""
import unittest
from unittest.mock import patch
from fractions import Fraction
import torch
from core.motion_context import apply_motion_context
from core.continuity import continuity_frame_budget, resolve_continuity
from core.audio_post import prepare_timeline_audio, slice_audio_frames


class MotionContextNumerical(unittest.TestCase):
    def setUp(self):
        self.previous={'samples':(torch.arange(1*2*72*2*2.).reshape(1,2,72,2,2),
                                  torch.arange(405.).reshape(1,1,1,405))}
        self.target={'samples':(torch.zeros((1,2,72,2,2)),torch.zeros((1,1,1,405)))}
        self.extra={'kind':'image','sentinel':object()}
        self.closing={'resolved_frame_index':242,'latent':torch.ones((1,2,1,2,2))}
        self.positive=[[torch.ones(1),{'minimax_refs':[self.extra],'minimax_keyframes':[self.closing]}]]

    def apply(self, **kwargs):
        return apply_motion_context(self.positive,self.target,previous_av=self.previous,
            previous_tail={},vae=None,audio_vae=None,context_frames=22,audio_frames=24,**kwargs)

    def test_exact_sampled_tail_guides_without_roundtrip_or_target_mutation(self):
        before=self.previous['samples'][0].clone()
        positive,trim,old_trim,source=self.apply()
        guides=positive[0][1]['minimax_keyframes']
        for index,offset in enumerate([0,1,5,9,13,17,18]):
            self.assertEqual(guides[index]['resolved_frame_index'],offset)
            self.assertTrue(torch.equal(guides[index]['latent'],before[:,:,65+index:66+index]))
        sound=guides[7]
        self.assertEqual(sound['resolved_frame_index'],-2.)
        self.assertTrue(torch.equal(sound['audio_latent'],self.previous['samples'][1][...,-40:]))
        self.assertEqual((trim,old_trim,source),(22,0,'sampled_latent'))
        self.assertIs(positive[0][1]['minimax_refs'][0],self.extra)
        self.assertIs(guides[-1],self.closing)
        self.assertEqual(len(self.positive[0][1]['minimax_keyframes']),1)
        guides[0]['latent'].zero_()
        self.assertTrue(torch.equal(self.previous['samples'][0],before))
        self.assertEqual(torch.count_nonzero(self.target['samples'][0]),0)
        self.assertNotIn('noise_mask',self.target)

    def test_signed_audio_phase_is_preserved(self):
        self.previous={'samples':(torch.ones((1,2,17,2,2)),torch.arange(93.).reshape(1,1,1,93))}
        positive,*_=self.apply()
        sound=next(g for g in positive[0][1]['minimax_keyframes'] if 'audio_latent' in g)
        self.assertAlmostEqual(sound['resolved_frame_index'],-2.2)
        self.assertEqual(sound['audio_latent'].shape[-1],40)

    def test_cropped_export_aligns_both_streams_to_same_source_endpoint(self):
        positive,trim,previous_trim,_=self.apply(context_end_frame=235)
        self.assertGreater(previous_trim,0)
        endpoint=235-previous_trim
        audio=next(g['audio_latent'] for g in positive[0][1]['minimax_keyframes'] if 'audio_latent' in g)
        end=round(endpoint*40/24)
        self.assertTrue(torch.equal(audio,self.previous['samples'][1][...,end-40:end]))
        self.assertEqual(trim,22)

    def test_pixel_fallback_only_when_no_compatible_latent(self):
        class VAE:
            def encode(self,frames):
                self.frames=frames
                return torch.ones((1,2,7,2,2))
        vae=VAE()
        with patch('core.motion_context._resize_frames',side_effect=lambda frames,*args:frames):
            positive,trim,previous_trim,source=apply_motion_context(self.positive,self.target,
                previous_av=None,previous_tail={'tail_frames':torch.zeros((22,32,32,3))},
                vae=vae,audio_vae=None,context_frames=22,audio_frames=0)
        self.assertEqual((trim,previous_trim,source),(22,0,'decoded_fallback'))
        self.assertFalse(any('audio_latent' in g for g in positive[0][1]['minimax_keyframes']))

    def test_duration_contract_and_independent_audio(self):
        self.assertEqual(continuity_frame_budget(243,22,'new'),(277,243))
        self.assertEqual(continuity_frame_budget(243,22,'total'),(243,221))
        self.assertEqual(resolve_continuity({'context_length':22,'audio_context_length':24})['audio_frames'],24)
        with self.assertRaises(ValueError):continuity_frame_budget(22,22,'total')

    def test_audio_boundaries_do_not_accumulate_rounding_drift(self):
        fps=Fraction(30000,1001)
        clips=[{'waveform':torch.ones((1,2,2003)),'sample_rate':48000,
                'frame_count':1,'fps':float(fps)} for _ in range(101)]
        segments=prepare_timeline_audio(clips,fade_ms=0,enable_gain_match=False)
        self.assertEqual(sum(x['waveform'].shape[-1] for x in segments),round(101*48000/float(fps)))
        self.assertGreater(len(set(x['waveform'].shape[-1] for x in segments)),1)
        wave=torch.arange(100000.).reshape(1,1,-1)
        sliced=slice_audio_frames({'waveform':wave,'sample_rate':48000},22,39)
        self.assertEqual(sliced['frame_count'],17)
        self.assertTrue(torch.equal(sliced['waveform'],wave[...,44000:78000]))
        self.assertTrue(torch.equal(sliced['seam_prefix']['waveform'],wave[...,:44000]))


if __name__=='__main__':unittest.main()
