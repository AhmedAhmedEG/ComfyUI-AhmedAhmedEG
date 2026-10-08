"""Pixel and optional RTX providers share the decoded video pipeline."""
import torch
import torch.nn.functional as F


class MiniMaxH3PixelUpscale:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"images": ("IMAGE",), "provider": (["bicubic", "learned_pixel", "RTX VSR", "RTX High Bitrate"],),
            "width": ("INT", {"default":1920,"min":32,"max":16384,"step":32}),
            "height": ("INT", {"default":1088,"min":32,"max":16384,"step":32}),
            "quality": (["Low","Medium","High","Ultra"],),
            "resize_method": (["Center Crop (Fill)","Letterbox (Fit)"],),
            "denoise": ("BOOLEAN", {"default":False}), "deblur": ("BOOLEAN", {"default":False})},
            "optional": {"upscale_model": ("UPSCALE_MODEL",)}}
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "upscale"
    CATEGORY = "ComfyUI-AhmedAhmedEG"

    def upscale(self, images, provider="bicubic", width=1920, height=1088, quality="High", resize_method="Center Crop (Fill)", denoise=False, deblur=False, upscale_model=None):
        if images.ndim != 4 or images.shape[0] < 1: raise ValueError("Pixel upscale needs an IMAGE batch.")
        if provider == "learned_pixel":
            if upscale_model is None: raise ValueError("Learned pixel upscale requires an UPSCALE_MODEL.")
            from comfy_extras.nodes_upscale_model import ImageUpscaleWithModel
            images = ImageUpscaleWithModel().upscale(upscale_model, images)[0]
        if provider in ("bicubic", "learned_pixel"):
            return (F.interpolate(images[..., :3].permute(0,3,1,2), size=(height,width), mode="bicubic", align_corners=False).permute(0,2,3,1).clamp(0,1),)
        if provider not in ("RTX VSR", "RTX High Bitrate"): raise ValueError("Unknown pixel provider.")
        if not torch.cuda.is_available(): raise RuntimeError("RTX processing requires an NVIDIA CUDA GPU and the nvvfx SDK.")
        try:
            from ..core.vendor.dasiwa.rtx_effects import _import_vfx, _maybe_vfx_effect, _run_vfx_effect, _fit_frame_to_target_aspect
        except ImportError:
            from core.vendor.dasiwa.rtx_effects import _import_vfx, _maybe_vfx_effect, _run_vfx_effect, _fit_frame_to_target_aspect
        api = _import_vfx(); device = torch.device("cuda"); index = torch.cuda.current_device()
        result = torch.empty((images.shape[0],height,width,3), dtype=torch.float32, device="cpu")
        from contextlib import ExitStack
        with ExitStack() as stack:
            clean = stack.enter_context(_maybe_vfx_effect(api, denoise, "Denoise", quality, index, images.shape[2], images.shape[1]))
            sharp = stack.enter_context(_maybe_vfx_effect(api, deblur, "Deblur", quality, index, images.shape[2], images.shape[1]))
            effect = stack.enter_context(_maybe_vfx_effect(api, True, "VSR" if provider == "RTX VSR" else "High Bitrate", quality, index, width,height))
            for position, image in enumerate(images):
                frame = image[..., :3].permute(2,0,1).to(device=device, dtype=torch.float32).contiguous()
                if clean: frame = _run_vfx_effect(clean,frame,device)
                if sharp: frame = _run_vfx_effect(sharp,frame,device)
                frame = _fit_frame_to_target_aspect(frame,width,height,resize_method)
                result[position] = _run_vfx_effect(effect,frame,device).permute(1,2,0).cpu().clamp(0,1)
        return (result,)
