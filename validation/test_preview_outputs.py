import json
import tempfile
import unittest
from unittest.mock import patch
import torch

from core.cache_manager import ProjectCacheManager
from nodes.node_smart_preview import MiniMaxH3SmartPreview


class PreviewOutputs(unittest.TestCase):
    def test_scope_outputs_have_exact_visible_frames_audio_and_source_fps(self):
        with tempfile.TemporaryDirectory() as folder,patch('core.cache_manager.get_cache_root_dir',return_value=folder):
            manager=ProjectCacheManager('outputs')
            state={'project_id':'outputs','clips':[{'id':'one'},{'id':'two'}]}
            for i,cid in enumerate(('one','two')):
                manager.store_clip_results(cid,cid,{'samples':torch.zeros(1)},
                    {'waveform':torch.ones(1,2,48000)*.1,'sample_rate':48000},
                    torch.full((24,16,32,3),.2+i*.5))
            manager.update_clip_metadata('two',{'trim_prefix':2,'previous_trim':1})
            graph={'rife':{'inputs':{'images':['17',0],'source_fps':['17',2]}}}
            for scope,count in [('latest',22),('full',45)]:
                out=MiniMaxH3SmartPreview().preview(json.dumps(state),json.dumps({'scope':scope}),graph,'17')['result']
                self.assertEqual(tuple(out[0].shape),(count,16,32,3))
                self.assertEqual(out[2],24.)
                self.assertAlmostEqual(out[1]['waveform'].shape[-1]/out[1]['sample_rate'],count/24,places=4)
            self.assertAlmostEqual(float(out[0][0].mean()),.2,places=5)
            self.assertAlmostEqual(float(out[0][-1].mean()),.7,places=5)

    def test_unwired_or_only_fps_output_does_not_load_raw_video(self):
        with patch('core.preview_outputs.load_preview_outputs',side_effect=AssertionError('Unneeded raw movie')):
            state=json.dumps({'project_id':'outputs','clips':[]})
            node=MiniMaxH3SmartPreview()
            self.assertEqual(node.preview(state)['result'],(None,None,24.))
            self.assertEqual(node.preview(state,prompt={'rife':{'inputs':{'source_fps':['17',2]}}},unique_id='17')['result'],(None,None,24.))


if __name__=='__main__':unittest.main()
