import tempfile
import unittest
from pathlib import Path
import av
import torch
from core.cache_manager import ProjectCacheManager
from core.preview import create_preview_plan
from core.preview_segments import encode_fragment


class PreviewSegments(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.manager=ProjectCacheManager('segments',self.temp.name)
        self.state={'project_id':'segments','clips':[{'id':'one'},{'id':'two'}]}
        for i,cid in enumerate(('one','two')):
            self.manager.store_clip_results(cid,cid,{'samples':torch.zeros(1,1,2,4,4)},
                {'waveform':torch.ones(1,2,48000)*(.1+i*.1),'sample_rate':48000},
                torch.full((24,32,64,3),.2+i*.5))
        self.manager.update_clip_metadata('two',{'trim_prefix':2,'previous_trim':1})
    def test_latest_and_full_share_video_and_have_exact_visible_duration(self):
        latest=create_preview_plan(self.state,'latest',self.temp.name)['playback']
        full=create_preview_plan(self.state,'full',self.temp.name)['playback']
        self.assertEqual(latest['videos'][0]['key'],full['videos'][1]['key'])
        self.assertAlmostEqual(full['duration'],45/24)
        self.assertAlmostEqual(full['videos'][0]['duration'],23/24)
        self.assertNotEqual(latest['audio']['key'],full['audio']['key'])
    def test_fragment_is_seekable_fmp4_and_codec_matches_browser_manifest(self):
        manifest=create_preview_plan(self.state,'full',self.temp.name)['playback']
        for part in manifest['videos']:
            path=encode_fragment('segments',part['key'],self.temp.name)
            self.assertIn(b'moof',Path(path).read_bytes())
            with av.open(path) as container:
                stream=container.streams.video[0]
                self.assertEqual(stream.codec_context.extradata[1:4].hex(),'640033')
                self.assertEqual(len(list(container.decode(video=0))),24 if part['clip_id']=='one' else 22)
            stamp=Path(path).stat().st_mtime_ns
            self.assertEqual(encode_fragment('segments',part['key'],self.temp.name),path)
            self.assertEqual(Path(path).stat().st_mtime_ns,stamp)
        path=encode_fragment('segments',manifest['audio']['key'],self.temp.name)
        with av.open(path) as container:
            self.assertEqual(len(container.streams.video),0)
            frames=list(container.decode(audio=0))
            self.assertAlmostEqual(sum(f.samples for f in frames)/48000,45/24,delta=.03)
    def test_regeneration_changes_only_replaced_video_revision(self):
        before=create_preview_plan(self.state,'full',self.temp.name)['playback']
        self.manager.store_clip_results('two','new',{'samples':torch.zeros(1,1,2,4,4)},decoded_frames=torch.zeros(24,32,64,3))
        after=create_preview_plan(self.state,'full',self.temp.name)['playback']
        self.assertEqual(before['videos'][0]['key'],after['videos'][0]['key'])
        self.assertNotEqual(before['videos'][1]['key'],after['videos'][1]['key'])

if __name__=='__main__':unittest.main()
