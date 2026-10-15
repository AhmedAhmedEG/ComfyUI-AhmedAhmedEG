"""Aspect-preserving IMAGE resize shared by decoded enhancement providers."""
import math
import torch
import torch.nn.functional as F


def resize_pixels(images, width, height, policy='Center Crop (Fill)', method='bicubic'):
    if policy not in ('Center Crop (Fill)', 'Letterbox (Fit)', 'Stretch'):
        raise ValueError('Unknown pixel resize policy.')
    if min(width,height)<1: raise ValueError('Pixel dimensions must be positive.')
    h,w=images.shape[1:3]
    scale=(max if policy=='Center Crop (Fill)' else min)(width/w,height/h)
    nw,nh=(width,height) if policy=='Stretch' else (max(1,round(w*scale)),max(1,round(h*scale)))
    if method=='lanczos':
        from PIL import Image
        import numpy as np
        # Float channels avoid quantizing latent-refinement preparation to 8 bits.
        rows=[]
        for image in images.detach().cpu():
            planes=[np.asarray(Image.fromarray(image[...,c].numpy().astype('float32')).resize((nw,nh),Image.Resampling.LANCZOS)).copy() for c in range(min(3,image.shape[-1]))]
            rows.append(torch.from_numpy(np.stack(planes,axis=-1)))
        result=torch.stack(rows).to(device=images.device,dtype=images.dtype).permute(0,3,1,2)
    else:
        result=F.interpolate(images[...,:3].permute(0,3,1,2),size=(nh,nw),mode='bicubic',align_corners=False)
    if policy=='Center Crop (Fill)':
        x,y=max(0,(nw-width)//2),max(0,(nh-height)//2)
        result=result[:,:,y:y+height,x:x+width]
    elif policy=='Letterbox (Fit)':
        x,y=(width-nw)//2,(height-nh)//2
        result=F.pad(result,(x,width-nw-x,y,height-nh-y))
    return result.permute(0,2,3,1).clamp(0,1)
