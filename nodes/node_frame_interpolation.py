"""Post-generation frame interpolation with an explicit time/audio contract."""
class MiniMaxH3FrameInterpolation:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'images':('IMAGE',),'fps':('FLOAT',{'default':24.,'min':1.,'max':120.}),
            'multiplier':('INT',{'default':2,'min':2,'max':8}),
            'provider':(['Linear','RTX'],), 'quality':(['LOW','MEDIUM','HIGH'],),
            'detect_cuts':('BOOLEAN',{'default':True})},'optional':{'audio':('AUDIO',)}}
    RETURN_TYPES=('IMAGE','AUDIO','FLOAT')
    RETURN_NAMES=('images','audio','fps')
    FUNCTION='interpolate'
    CATEGORY='ComfyUI-AhmedAhmedEG/Output'
    def interpolate(self,images,fps=24.,multiplier=2,provider='Linear',quality='HIGH',detect_cuts=True,audio=None):
        import math,torch
        if images.ndim!=4 or images.shape[0]<2: raise ValueError('Interpolation needs at least two frames.')
        if not math.isfinite(fps) or not 1<=fps<=120 or not 2<=multiplier<=8: raise ValueError('Invalid interpolation rate.')
        if provider=='RTX':
            try:
                from ..core.vendor.dasiwa.rtx_frame_generation import DaSiWa_RTX_FrameGeneration
            except ImportError:
                from core.vendor.dasiwa.rtx_frame_generation import DaSiWa_RTX_FrameGeneration
            result=DaSiWa_RTX_FrameGeneration().dasiwa_rtx_generate_frames(images,multiplier=multiplier,mode=quality,
                automatic_shot_change_detection=detect_cuts)[0]
        elif provider=='Linear':
            rows=[]
            for index in range(images.shape[0]-1):
                try:
                    import comfy.model_management as manager
                    manager.throw_exception_if_processing_interrupted()
                except ImportError: pass
                # A hard cut must not turn into a dissolve. Use a conservative
                # normalized mean pixel difference for the CPU fallback.
                cut=detect_cuts and float((images[index:index+1]-images[index+1:index+2]).abs().mean())>.3
                for step in range(multiplier):
                    rows.append(images[index:index+1] if cut else images[index:index+1]*(1-step/multiplier)+images[index+1:index+2]*(step/multiplier))
            result=torch.cat([*rows,images[-1:]],dim=0)
        else: raise ValueError('Unknown interpolation provider.')
        # Preserve container duration as well as endpoint intervals: the final
        # source frame retains a full source-frame hold at the faster rate.
        result=torch.cat([result,*[images[-1:] for _ in range(multiplier-1)]],dim=0)
        try:
            from ..core.audio_post import fit_audio_duration
        except ImportError:
            from core.audio_post import fit_audio_duration
        output_fps=fps*multiplier
        if audio is None: audio={'waveform':torch.zeros((1,2,round(result.shape[0]/output_fps*48000))),'sample_rate':48000}
        return result,fit_audio_duration(audio,result.shape[0],output_fps),float(output_fps)
