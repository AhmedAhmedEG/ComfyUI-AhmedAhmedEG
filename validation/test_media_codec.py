"""Actual PyAV codec and PCM round trips with tiny generated media."""
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import torch
import av


class MediaCodec(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        folder = types.ModuleType("folder_paths")
        folder.get_output_directory = lambda: str(root)
        folder.get_temp_directory = lambda: str(root)
        folder.get_input_directory = lambda: str(root)
        def save_path(prefix, output_dir, *dimensions):
            path = Path(output_dir)/prefix; path.parent.mkdir(parents=True,exist_ok=True)
            counter = len(list(path.parent.glob(path.name+"_*")))+1
            return str(path.parent), path.name, counter, str(path.parent.relative_to(root)), prefix
        folder.get_save_image_path = save_path
        utils = types.ModuleType("comfy.utils")
        class Progress:
            def __init__(self, total): pass
            def update_absolute(self, value): pass
        utils.ProgressBar = Progress
        comfy = types.ModuleType("comfy"); comfy.utils = utils
        modules = patch.dict(sys.modules,{"folder_paths":folder,"comfy":comfy,"comfy.utils":utils})
        modules.start(); self.addCleanup(modules.stop)
        # The encoder owns its module reference to folder_paths across imports.
        from core.vendor.dasiwa import enhanced_video
        runtime = patch.object(enhanced_video,"folder_paths",folder); runtime.start(); self.addCleanup(runtime.stop)
        encoders = patch.dict(enhanced_video._ENCODER_NAMES,{"H.264":("libx264",)}); encoders.start(); self.addCleanup(encoders.stop)
        self.encoder = enhanced_video.DaSiWa_EnhancedVideoCombine()

    def encode(self, images, depth="8-bit", audio=None):
        return self.encoder.combine(images,24.,"H.264","MP4",depth,18,False,True,"codec",True,True,
            audio=audio,prompt={"test":"roundtrip"},extra_pnginfo={"workflow":{"nodes":[]}})

    def test_true_ten_bit_video_and_audio_round_trip(self):
        frames = torch.linspace(0,1,4*32*32*3).reshape(4,32,32,3)
        audio = {"waveform":torch.zeros((1,2,8000)),"sample_rate":48000}
        result = self.encode(frames,"10-bit",audio)
        with av.open(result["result"][1]) as container:
            self.assertEqual(container.streams.video[0].codec_context.format.name,"yuv420p10le")
            self.assertEqual(len(container.streams.audio),1)
            self.assertEqual(len(list(container.decode(video=0))),4)
            self.assertIn("prompt",container.metadata)

    def test_input_media_loader_reads_encoded_frames_and_audio(self):
        from core.media_io import load_video,load_audio
        frames = torch.ones((24,32,32,3))*.5
        audio = {"waveform":torch.ones((1,2,48000))*.1,"sample_rate":48000}
        result = self.encode(frames,audio=audio)
        name = Path(result["result"][1]).name
        loaded = load_video(name,self.temp.name,trim_start=.25,trim_end=.75,target_fps=24)
        sound = load_audio(name,self.temp.name,trim_start=.25,trim_end=.75)
        self.assertEqual(loaded.shape,(12,32,32,3))
        self.assertEqual(sound["waveform"].shape[-1],24000)

    def test_explicit_audio_codec_is_not_silently_changed(self):
        result = self.encoder.combine(torch.zeros((4,32,32,3)),24.,"H.264","MKV","8-bit",18,False,False,"explicit",True,False,
            audio={"waveform":torch.zeros((1,2,8000)),"sample_rate":48000},audio_codec="FLAC")
        with av.open(result["result"][1]) as container:
            self.assertEqual(container.streams.audio[0].codec_context.name, "flac")
