"""Actual MP4 encode/concat and repeat-export invalidation, no model weights."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import av
import imageio_ffmpeg
import torch
from core.cache_manager import ProjectCacheManager
from core.vendor.dasiwa.helper_pyav_video import encode_attempt
from nodes.node_project_video import MiniMaxH3ProjectVideo


class SegmentExportCache(unittest.TestCase):
    def test_repeat_export_reuses_encoded_segments_and_audio_settings_invalidate(self):
        with tempfile.TemporaryDirectory() as root:
            manager=ProjectCacheManager('segments',root)
            frames=torch.rand((24,32,64,3))
            audio={'waveform':torch.zeros((1,2,48000)),'sample_rate':48000}
            for cid in ('one','two'):
                manager.store_clip_results(cid,'fixture',None,audio,frames)
            state={'project_id':'segments','clips':[{'id':'one'},{'id':'two'}]}
            calls=[]
            def combine(_self,pixels,**kw):
                target=Path(root)/f'encoded{len(calls)}.mp4'
                calls.append(str(target))
                encode_attempt(str(target),'MP4','libx264',64,32,24,8,23,
                    lambda:((f.clamp(0,1).numpy()*255).round().astype('uint8') for f in pixels),
                    audio=(kw['audio']['waveform'][0].numpy(),48000),audio_encoder='aac')
                return {'result':(None,str(target)),'ui':{'video':[]}}
            def resolve(*args):return str(Path(root)/'assembled.mp4'),'assembled.mp4',''
            api=SimpleNamespace(InputImpl=SimpleNamespace(VideoFromFile=lambda p:p))
            with patch.dict(sys.modules,{'comfy_api.latest':api}), \
                    patch('nodes.node_project_video.ProjectCacheManager',return_value=manager), \
                    patch('nodes.node_project_video.MiniMaxH3VideoCombine.combine_video',combine), \
                    patch('nodes.node_project_video.resolve_output_path',resolve), \
                    patch('nodes.node_project_video.FFMPEG_PATH',imageio_ffmpeg.get_ffmpeg_exe()):
                node=MiniMaxH3ProjectVideo()
                result=node.export(json.dumps(state),'segments',export_individual_shots=False)
                self.assertEqual(len(calls),2)
                with av.open(result['result'][0]) as video:
                    self.assertEqual(sum(1 for _ in video.decode(video=0)),48)
                node.export(json.dumps(state),'segments',export_individual_shots=False)
                self.assertEqual(len(calls),2,'No unchanged clip should be encoded twice')
                state['audio_fade_ms']=0
                node.export(json.dumps(state),'segments',export_individual_shots=False)
                self.assertEqual(len(calls),4,'Changed audio finishing invalidates cached encoded segments')


if __name__=='__main__':unittest.main()
