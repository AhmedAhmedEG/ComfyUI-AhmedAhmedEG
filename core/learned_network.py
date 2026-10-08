"""Strict learned network architecture with bounded temporal forward windows."""
import torch
from .vendor.dasiwa.h3_latent_upscale import _LatentResizer3D


class ValidatedH3Resizer(_LatentResizer3D):
    def forward(self, x, scale, target_size, enable_chunking=False):
        # GroupNorm/attention couple time globally, so chunked inference is an
        # explicit approximation. Halos retain the convolutional context.
        halo = sum((module.kernel_size[0]-1)//2 for module in self.modules() if isinstance(module, torch.nn.Conv3d))
        chunk = 24
        total = x.shape[2]
        if not enable_chunking or total <= chunk+2*halo:
            return super().forward(x, scale, target_size)
        output = x.new_empty((x.shape[0],x.shape[1],total,target_size[-2],target_size[-1]))
        for start in range(0,total,chunk):
            end = min(total,start+chunk); left = max(0,start-halo); right = min(total,end+halo)
            part = super().forward(x[:,:,left:right],scale,(right-left,*target_size[-2:]))
            output[:,:,start:end] = part[:,:,start-left:end-left]
        return output
