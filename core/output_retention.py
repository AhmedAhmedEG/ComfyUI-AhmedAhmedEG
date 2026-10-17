"""Bound decoded result retention without changing disk-backed project takes."""
class LatestClipBuffer(list):
    def append(self, value):
        self.clear()
        super().append(value)


def output_buffers(policy):
    if policy=='full':return [],[]
    if policy=='latest':return LatestClipBuffer(),LatestClipBuffer()
    raise ValueError('Decoded output must be full or latest.')


def process_video_frames(frames, directory, operation):
    """Finalize pixels in bounded windows into reclaimable disk storage."""
    from .vendor.dasiwa.helper_batch_output import allocate_cpu_output
    from .run_resources import current_resources
    output, path = allocate_cpu_output(tuple(frames.shape), frames.dtype, directory, force_mmap=True)
    owner = current_resources()
    if owner is not None and path:
        owner.paths.append(path)
    window = max(1, min(16, (32 * 1024**2) // max(1, frames[0].numel()*4)))
    for start in range(0, int(frames.shape[0]), window):
        output[start:start+window].copy_(operation(frames[start:start+window]))
    return output


def assemble_frames(chunks, directory, canvas=None):
    """Copy bounded frame windows into one budgeted IMAGE output, RAM or disk."""
    import torch
    import torch.nn.functional as F
    from .vendor.dasiwa.helper_batch_output import allocate_cpu_output
    from .memory_lifecycle import reclaim_host_memory
    if not chunks:
        raise ValueError('No decoded frames to assemble.')
    height = max(int(f.shape[1]) for f in chunks)
    width = max(int(f.shape[2]) for f in chunks)
    if canvas is not None:
        width, height = canvas
    count = sum(int(f.shape[0]) for f in chunks)
    dtype = chunks[0].dtype
    for f in chunks[1:]:
        dtype = torch.promote_types(dtype, f.dtype)
    shape = (count, height, width, int(chunks[0].shape[-1]))
    required = count * height * width * shape[-1] * torch.empty((), dtype=dtype).element_size()
    # Large raw full-video outputs stay disk-backed even if idle RAM looks
    # generous: the next graph node and native models need working headroom.
    force_disk = required > 256 * 1024**2
    if not force_disk:
        reclaim_host_memory(required)
    output, _ = allocate_cpu_output(shape, dtype, directory, force_mmap=force_disk)
    offset = 0
    for frames in chunks:
        ih, iw = int(frames.shape[1]), int(frames.shape[2])
        # Resizing an entire clip creates a second giant RGB allocation.
        window = max(1, min(16, (32 * 1024**2) // max(1, height * width * shape[-1] * 4)))
        for start in range(0, int(frames.shape[0]), window):
            pixels = frames[start:start+window]
            if (ih, iw) != (height, width):
                scale = min(width / iw, height / ih)
                nh, nw = max(1, round(ih*scale)), max(1, round(iw*scale))
                pixels = F.interpolate(pixels.permute(0, 3, 1, 2), size=(nh, nw), mode='bilinear', align_corners=False)
                px, py = (width-nw)//2, (height-nh)//2
                pixels = F.pad(pixels, (px, width-nw-px, py, height-nh-py)).permute(0, 2, 3, 1)
            length = int(pixels.shape[0])
            output[offset:offset+length].copy_(pixels)
            offset += length
    return output
