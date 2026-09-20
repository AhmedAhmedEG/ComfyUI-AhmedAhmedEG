"""Face tracking, close-up crop refinement, and seamless feather stitching."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np
import torch
import torch.nn.functional as F

from .config import snap_to_multiple, CANVAS_MULTIPLE

log = logging.getLogger("MiniMaxH3MasterDirector.face_refine")


def generate_feathered_ellipse_mask(h: int, w: int, feather: int = 16) -> torch.Tensor:
    """Generate a smooth elliptical alpha mask for seamless face pasting."""
    y = torch.linspace(-1.0, 1.0, h).view(h, 1)
    x = torch.linspace(-1.0, 1.0, w).view(1, w)
    dist = torch.sqrt(x ** 2 + y ** 2)

    mask = (1.0 - dist).clamp(0.0, 1.0)
    # Smooth step
    mask = mask * mask * (3.0 - 2.0 * mask)
    return mask.unsqueeze(0).unsqueeze(-1)  # [1, H, W, 1]


def simple_face_detect_bbox(frame: torch.Tensor) -> Tuple[int, int, int, int]:
    """Fallback bounding box locator if OpenCV or YOLO face detector is unavailable (centers on upper 40%)."""
    h, w = frame.shape[0], frame.shape[1]
    box_size = min(h, w) // 2
    box_size = snap_to_multiple(box_size, CANVAS_MULTIPLE)

    center_y = int(h * 0.38)
    center_x = int(w * 0.5)

    x1 = max(0, min(w - box_size, center_x - box_size // 2))
    y1 = max(0, min(h - box_size, center_y - box_size // 2))
    return x1, y1, box_size, box_size


_DETECTOR_CACHE: Dict[str, Any] = {}


def load_ultralytics_detector(name: str = "face_yolov8m.pt"):
    """Attempt to load a YOLO face detector from ComfyUI models/ultralytics directory."""
    if name in _DETECTOR_CACHE:
        return _DETECTOR_CACHE[name]

    try:
        import folder_paths
        import os
        path = None
        for key in ("ultralytics_bbox", "ultralytics"):
            try:
                path = folder_paths.get_full_path(key, name)
            except Exception:
                path = None
            if path:
                break
        if path is None:
            base = getattr(folder_paths, "models_dir", "models")
            for sub in ("ultralytics/bbox", "ultralytics", "ultralytics/segm"):
                cand = os.path.join(base, *sub.split("/"), name)
                if os.path.isfile(cand):
                    path = cand
                    break
        if path is None or not os.path.isfile(path):
            return None

        from ultralytics import YOLO
        model = YOLO(path)
        _DETECTOR_CACHE[name] = model
        return model
    except Exception as exc:
        log.debug(f"Ultralytics face detector '{name}' not loaded: {exc}")
        return None


def detect_face_bbox_ultralytics(
    frame: torch.Tensor,
    detector_name: str = "face_yolov8m.pt",
) -> Optional[Tuple[int, int, int, int]]:
    """Detect face bounding box using Ultralytics YOLO if available."""
    detector = load_ultralytics_detector(detector_name)
    if detector is None:
        return None

    try:
        # Convert frame [H, W, C] in range [0, 1] RGB to BGR uint8
        arr = (frame[..., :3].clamp(0, 1).detach().cpu().numpy() * 255.0).astype(np.uint8)
        bgr = arr[..., ::-1].copy()
        results = detector(bgr, conf=0.35, verbose=False)
        if not results or len(results) == 0:
            return None
        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            return None

        xyxy = boxes.xyxy.cpu().numpy()
        best_box = None
        max_area = -1.0
        for box in xyxy:
            bx0, by0, bx1, by1 = box[:4]
            area = (bx1 - bx0) * (by1 - by0)
            if area > max_area:
                max_area = area
                best_box = (bx0, by0, bx1, by1)

        if best_box is None:
            return None

        bx0, by0, bx1, by1 = best_box
        bw = bx1 - bx0
        bh = by1 - by0
        cx = bx0 + bw * 0.5
        cy = by0 + bh * 0.5
        box_size = int(max(bw, bh) * 2.0)
        h, w = frame.shape[0], frame.shape[1]
        box_size = snap_to_multiple(min(box_size, min(h, w)), CANVAS_MULTIPLE)

        x1 = max(0, min(w - box_size, int(cx - box_size // 2)))
        y1 = max(0, min(h - box_size, int(cy - box_size // 2)))
        return x1, y1, box_size, box_size
    except Exception as exc:
        log.debug(f"Ultralytics inference error, falling back to simple heuristic: {exc}")
        return None


def apply_face_refinement(
    decoded_frames: torch.Tensor,
    model=None,
    vae=None,
    clip=None,
    seed: int = 0,
    prompt: str = "cinematic close-up portrait of face, sharp focus, natural skin texture",
    strength: float = 0.35,
    crop_size: int = 512,
    detector_name: str = "face_yolov8m.pt",
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Crop tracked face, sample fine facial details, and feather-stitch back."""
    if decoded_frames is None or decoded_frames.ndim != 4:
        return decoded_frames, decoded_frames

    orig_frames = decoded_frames.clone()
    t, h, w, c = decoded_frames.shape

    # Crop coordinates: try YOLO face detector first, fallback to center heuristic
    yolo_box = detect_face_bbox_ultralytics(decoded_frames[0], detector_name=detector_name)
    if yolo_box is not None:
        x1, y1, cw, ch = yolo_box
    else:
        x1, y1, cw, ch = simple_face_detect_bbox(decoded_frames[0])
    cw = snap_to_multiple(min(cw, crop_size, w), CANVAS_MULTIPLE)
    ch = snap_to_multiple(min(ch, crop_size, h), CANVAS_MULTIPLE)
    x1 = max(0, min(w - cw, x1))
    y1 = max(0, min(h - ch, y1))

    face_crops = decoded_frames[:, y1 : y1 + ch, x1 : x1 + cw, :3].contiguous()

    refined_crops = face_crops.clone()

    # If VAE and model are present, execute full latent resampling pass
    if vae is not None and model is not None and strength > 0.01:
        try:
            log.info(f"FaceRefine: Refining {t} frames of face crop ({cw}x{ch}) with denoise={strength:.2f}...")
            encoded = vae.encode(face_crops)
            if hasattr(encoded, "get") and "samples" in encoded:
                crop_latent_tensor = encoded["samples"]
            else:
                crop_latent_tensor = encoded

            # Ensure proper 5D shape [1, C, T, H, W]
            if crop_latent_tensor.ndim == 4:
                crop_latent_tensor = crop_latent_tensor.unsqueeze(0).movedim(1, 2)

            # Build conditioning for face prompt
            positive = []
            if clip is not None:
                try:
                    tokens = clip.tokenize(prompt)
                    cond, pooled = clip.encode_from_tokens(tokens, return_pooled=True)
                    positive = [[cond, {"pooled_output": pooled}]]
                except Exception:
                    pass

            # If positive is empty, create minimal conditioning
            if not positive:
                dummy_cond = torch.zeros((1, 1, 5120), device=crop_latent_tensor.device)
                positive = [[dummy_cond, {}]]

            # Pack latent
            try:
                import comfy.nested_tensor
                # Add dummy audio stream to satisfy H3 AV UNET requirements if needed
                audio_latent = torch.zeros((1, 32, 2, max(1, round(t / 24.0 * 40))), device=crop_latent_tensor.device)
                samples = comfy.nested_tensor.NestedTensor((crop_latent_tensor, audio_latent))
            except Exception:
                samples = crop_latent_tensor

            latent_dict = {"samples": samples}

            import comfy.sample
            steps = max(4, int(20 * strength))
            sampled = comfy.sample.sample(
                model,
                latent_dict,
                steps=steps,
                cfg=1.0,
                sampler_name="euler",
                scheduler="simple",
                positive=positive,
                negative=[],
                seed=seed,
                denoise=strength,
            )

            res_samples = sampled.get("samples", sampled)
            from .continuity import unpack_av_samples
            res_streams, _ = unpack_av_samples(res_samples)
            res_video = res_streams[0]

            decoded = vae.decode(res_video)
            if decoded.ndim == 5:
                decoded = decoded.reshape(-1, decoded.shape[-3], decoded.shape[-2], decoded.shape[-1])
            refined_crops = decoded[:t, ..., :3].to(orig_frames.device).float()
        except Exception as exc:
            log.warning(f"FaceRefine latent sample skipped ({exc}); applying guided detail enhancement.")
            # High-frequency guided unsharp enhancement fallback
            blurred = F.avg_pool2d(face_crops.permute(0, 3, 1, 2), kernel_size=5, stride=1, padding=2).permute(0, 2, 3, 1)
            high_freq = face_crops - blurred
            refined_crops = (face_crops + high_freq * (strength * 1.5)).clamp(0.0, 1.0)
    else:
        # Subtle unsharp enhancement when model is not provided
        blurred = F.avg_pool2d(face_crops.permute(0, 3, 1, 2), kernel_size=5, stride=1, padding=2).permute(0, 2, 3, 1)
        high_freq = face_crops - blurred
        refined_crops = (face_crops + high_freq * (strength * 1.5)).clamp(0.0, 1.0)

    # Ensure refined_crops matches target crop dimensions exactly
    if refined_crops.shape[1] != ch or refined_crops.shape[2] != cw:
        rc_t = refined_crops.permute(0, 3, 1, 2)
        rc_t = F.interpolate(rc_t, size=(ch, cw), mode="bilinear", align_corners=False)
        refined_crops = rc_t.permute(0, 2, 3, 1)

    # Blend refined face crop back into original frame batch with feathered elliptical mask
    mask = generate_feathered_ellipse_mask(ch, cw).to(orig_frames.device)
    stitched = orig_frames.clone()
    stitched[:, y1 : y1 + ch, x1 : x1 + cw, :3] = (
        refined_crops * mask + orig_frames[:, y1 : y1 + ch, x1 : x1 + cw, :3] * (1.0 - mask)
    )

    return stitched, orig_frames
