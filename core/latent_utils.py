"""Spatial tensor operations shared by refinement and numerical checks."""
import torch.nn.functional as F


def spatial_interpolate_video_latent(latent_tensor, target_h, target_w, mode="bilinear"):
    """Resize B,C,T,H,W spatially while retaining the time/channel axes."""
    b, c, t, h, w = latent_tensor.shape
    flat = latent_tensor.permute(0, 2, 1, 3, 4).reshape(b*t, c, h, w)
    options = {} if mode in ("nearest", "nearest-exact", "area") else {"align_corners":False}
    resized = F.interpolate(flat,size=(target_h,target_w),mode=mode,**options)
    return resized.reshape(b,t,c,target_h,target_w).permute(0,2,1,3,4).contiguous()
