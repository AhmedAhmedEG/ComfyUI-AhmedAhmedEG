"""Tracked crop refinement uses native joint AV conditioning and sampling."""
import torch
from .config import FPS, align_frame_count
from .executor import MasterDirectorExecutor, decode_video_latent
from .continuity import extract_streams_from_av_latent
from .advanced_sampling import sample_stage


def refine_tracked_faces(frames, model, video_vae, audio_vae, clip, seed, settings,
                         cfg=1., ref_images=None, continuity=False):
    from .vendor.aimixer.director.face_refine.pack import pack_face_refine
    from .vendor.aimixer.director.face_refine.track import track_and_crop
    from .vendor.aimixer.director.face_refine.inject import inject_video_latent
    from .vendor.aimixer.director.face_refine.stitch import stitch_faces, fade_stitch_at_seams
    options = {key: value for key, value in settings.items() if key in (
        "detector", "confidence", "crop_factor", "canvas_width", "canvas_height", "canvas_mode",
        "select", "denoise", "steps", "sampler", "scheduler", "seed_mode", "paste_region",
        "mask_dilation", "feather", "colour_match", "blend", "sigmas")}
    options.setdefault("denoise", settings.get("strength", .35))
    options.setdefault("canvas_width", settings.get("crop_size", 512))
    options.setdefault("canvas_height", settings.get("crop_size", 512))
    pack = pack_face_refine(**options)
    base = frames[..., :3].float().cpu()
    crops, transform, note = track_and_crop(base, pack)
    if crops is None: return frames, note
    width, height = transform["canvas"]
    count = align_frame_count(crops.shape[0])
    if crops.shape[0] < count:
        crops = torch.cat([crops, crops[-1:].expand(count-crops.shape[0], -1, -1, -1)], dim=0)
    positive, latent, _ = MasterDirectorExecutor().build_conditioning("REF2VA",
        settings.get("prompt", "detailed natural face"), width, height, count/FPS,
        clip, video_vae, audio_vae, ref_images=ref_images)
    latent = inject_video_latent(latent, crops, video_vae)
    negative = [[torch.zeros_like(embedding), dict(metadata)] for embedding, metadata in positive]
    sampled = sample_stage(model, latent, pack["steps"], cfg, pack["sampler"], pack["scheduler"],
        positive, negative, (seed + 1 if pack["seed_mode"] == "offset" else seed) & ((1 << 64)-1),
        pack["denoise"], sigmas=pack.get("sigmas_tensor"))
    video, _ = extract_streams_from_av_latent(sampled)
    refined = decode_video_latent(video_vae, video)
    if refined.shape[0] < base.shape[0]:
        refined = torch.cat([refined, refined[-1:].expand(base.shape[0]-refined.shape[0], -1, -1, -1)], dim=0)
    result = stitch_faces(base, refined[:base.shape[0]], transform, pack)
    if continuity:
        result = fade_stitch_at_seams(result, base, head_frames=12, tail_frames=12)
    return result, note
