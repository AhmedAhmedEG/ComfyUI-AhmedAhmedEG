try:
    from ..core.output_processing import playback, watermark, seamless_loop
except ImportError:
    from core.output_processing import playback, watermark, seamless_loop


class MiniMaxH3OutputProcessing:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"images": ("IMAGE",), "source_fps": ("FLOAT", {"default":24.,"min":1.,"max":240.}),
            "playback_fps": ("FLOAT", {"default":24.,"min":1.,"max":240.}), "playback_policy": (["resample", "retime"],),
            "watermark_text": ("STRING", {"default":""}), "opacity": ("FLOAT", {"default":.5,"min":0.,"max":1.}),
            "corner": (["bottom_right", "bottom_left", "top_right", "top_left"],),
            "loop_overlap_frames": ("INT", {"default":0,"min":0,"max":1000})},
            "optional": {"audio": ("AUDIO",), "logo": ("IMAGE",)}}
    RETURN_TYPES = ("IMAGE", "AUDIO", "FLOAT")
    FUNCTION = "process"
    CATEGORY = "ComfyUI-AhmedAhmedEG"

    def process(self, images, source_fps=24., playback_fps=24., playback_policy="resample", watermark_text="", opacity=.5, corner="bottom_right", loop_overlap_frames=0, audio=None, logo=None):
        frames, audio = playback(images, audio, source_fps, playback_fps, playback_policy)
        frames = watermark(frames, watermark_text, logo, opacity, corner)
        if loop_overlap_frames: frames, audio = seamless_loop(frames, audio, playback_fps, loop_overlap_frames)
        return (frames, audio, playback_fps)
