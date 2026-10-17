"""Real tensors: durable output retention and seam allocation behavior."""
import gc
import tempfile
import unittest
import weakref
from pathlib import Path
import torch
from core.cache_manager import ProjectCacheManager, load_frame_tensor
from core.continuity import match_color_temperature_and_grade


class MemoryRetention(unittest.TestCase):
    def test_saved_frame_mapping_releases_original_and_preserves_full_output(self):
        with tempfile.TemporaryDirectory() as root:
            manager=ProjectCacheManager('memory',root)
            output=[]; expected=[]
            for i in range(4):
                frames=torch.rand((22,32,64,3))
                expected.append(frames.clone())
                original=weakref.ref(frames)
                output.append(frames)
                manager.store_clip_results(str(i),'fixture',None,decoded_frames=frames)
                output[-1]=manager.load_clip_frames(str(i))
                del frames
                gc.collect()
                self.assertIsNone(original(),'Output list must not retain decoded allocation')
                self.assertTrue(torch.equal(output[-1],expected[-1]))
            self.assertTrue(torch.equal(torch.cat(output),torch.cat(expected)))
            # Private mappings may be read/edited without rewriting durable takes.
            output[0].zero_()
            self.assertTrue(torch.equal(manager.load_clip_frames('0'),expected[0]))

    def test_spooling_releases_decode_before_audio_and_cleans_on_error(self):
        from core.run_resources import execution_resources, spill_frames, current_resources
        with tempfile.TemporaryDirectory() as root:
            refs=[]
            @execution_resources
            def run(fail=False):
                pixels=torch.rand((22,32,64,3));expected=pixels.clone();original=weakref.ref(pixels)
                pixels=spill_frames(pixels,root)
                gc.collect()
                self.assertIsNone(original(),'AudioVAE must not overlap the decoded anonymous tensor')
                self.assertTrue(torch.equal(pixels,expected))
                refs.extend(current_resources().paths)
                if fail:raise RuntimeError('audio decoder failed')
            run()
            with self.assertRaisesRegex(RuntimeError,'audio decoder failed'):run(True)
            self.assertTrue(all(not Path(path).exists() for path in refs))

    def test_budgeted_assembly_preserves_mixed_canvas_and_dtype(self):
        import torch.nn.functional as F
        from core.output_retention import assemble_frames
        with tempfile.TemporaryDirectory() as root:
            small=torch.rand((5,32,64,3),dtype=torch.float32)
            large=torch.rand((8,64,96,3),dtype=torch.float16)
            pixels=F.interpolate(small.permute(0,3,1,2),size=(48,96),mode='bilinear',align_corners=False)
            expected=torch.cat([F.pad(pixels,(0,0,8,8)).permute(0,2,3,1),large],0)
            actual=assemble_frames([small,large],root)
            self.assertTrue(torch.equal(actual,expected))

    def test_large_assembly_maps_output_and_removes_file_when_released(self):
        from core.output_retention import assemble_frames
        # Expanded source has negligible backing storage; output exceeds 256 MiB.
        with tempfile.TemporaryDirectory() as root:
            source=torch.tensor(.25).expand(350,256,256,3)
            result=assemble_frames([source],root)
            files=list(Path(root).glob('*.mmap'))
            self.assertEqual(len(files),1)
            self.assertTrue(torch.all(result==.25))
            del result;gc.collect()
            self.assertFalse(files[0].exists())

    def test_chunked_color_and_owned_seam_are_pixel_identical(self):
        from core.output_retention import process_video_frames
        from core.references import edit_images
        from core.run_resources import execution_resources
        with tempfile.TemporaryDirectory() as root:
            @execution_resources
            def run():
                source=torch.rand((39,32,64,3));previous=torch.rand((22,32,64,3))
                color={'exposure':.2,'contrast':1.1,'saturation':.8}
                expected=match_color_temperature_and_grade(edit_images(source,color),previous)
                actual=process_video_frames(source,root,lambda x:edit_images(x,color))
                actual=match_color_temperature_and_grade(actual,previous,inplace=True)
                self.assertTrue(torch.equal(actual,expected))
            run()
            self.assertFalse(list(Path(root).glob('*.mmap')))

    def test_latest_output_reuses_its_private_mapped_clip_without_assembly(self):
        from core.output_retention import assemble_frames
        with tempfile.TemporaryDirectory() as root:
            manager=ProjectCacheManager('single',root)
            original=torch.rand((22,32,64,3))
            manager.store_clip_results('one','fixture',None,decoded_frames=original)
            view=manager.load_clip_frames('one')[5:]
            output=assemble_frames([view],root,reuse_single=True)
            self.assertIs(output,view)
            self.assertFalse(list(Path(root).glob('*.mmap')),'Latest output must not allocate a second output file')
            output.zero_()
            self.assertTrue(torch.equal(manager.load_clip_frames('one'),original))

    def test_legacy_frames_fallback_does_not_change_pixels(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'legacy.pt';pixels=torch.rand((5,8,8,3))
            torch.save(pixels,path,_use_new_zipfile_serialization=False)
            self.assertTrue(torch.equal(load_frame_tensor(path),pixels))

    def test_seam_matches_previous_math_without_mutating_input(self):
        current=torch.rand((39,32,64,3));previous=torch.rand((22,32,64,3))
        saved=current.clone();gain=(previous[-10:].float().mean((0,1,2))/(current[:10].float().mean((0,1,2))+1e-6)).clamp(.7,1.4)
        expected=current.clone().float();ramp=torch.linspace(1.,0.,12).view(-1,1,1,1)
        expected[:12]=expected[:12]*(1.+ramp*(gain.view(1,1,1,-1)-1.))
        expected=expected.clamp(0,1)
        actual=match_color_temperature_and_grade(current,previous)
        self.assertTrue(torch.equal(actual,expected))
        self.assertTrue(torch.equal(current,saved))


if __name__=='__main__':unittest.main()
