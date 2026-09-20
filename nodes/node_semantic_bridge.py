"""MiniMax H3 Director Semantic Bridge node.

Rewrites official CONDITIONING tokens using a student MLP adapter.
"""

from __future__ import annotations

import glob
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

log = logging.getLogger("MiniMaxH3MasterDirector.semantic_bridge")

MMX_DIR_SEMANTIC_BRIDGE = "MMX_DIR_SEMANTIC_BRIDGE"
SEMANTIC_BRIDGE_FOLDER = "semantic_bridge"
MISSING_ADAPTER_LABEL = "(Place Semantic Bridge weights into models/semantic_bridge)"

HIDDEN_DIM = 5120
STUDENT_DIM = 512
DEFAULT_ALPHA = 0.15

_MODEL_CACHE: Dict[str, nn.Module] = {}


class SemanticStudent(nn.Module):
    """5120 -> 512 SiLU -> 512 SiLU -> 5120. Six tensors: fc1/2/3 weight+bias."""

    def __init__(self) -> None:
        super().__init__()
        self.fc1 = nn.Linear(HIDDEN_DIM, STUDENT_DIM)
        self.fc2 = nn.Linear(STUDENT_DIM, STUDENT_DIM)
        self.fc3 = nn.Linear(STUDENT_DIM, HIDDEN_DIM)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc3(F.silu(self.fc2(F.silu(self.fc1(x)))))


def ensure_semantic_bridge_folder() -> Optional[str]:
    try:
        import folder_paths
        if SEMANTIC_BRIDGE_FOLDER not in folder_paths.folder_names_and_paths:
            folder_paths.add_model_folder_path(
                SEMANTIC_BRIDGE_FOLDER,
                os.path.join(folder_paths.models_dir, SEMANTIC_BRIDGE_FOLDER),
            )
        paths = folder_paths.get_folder_paths(SEMANTIC_BRIDGE_FOLDER)
        return paths[0] if paths else None
    except Exception:
        return None


def list_semantic_bridge_adapters() -> List[str]:
    root = ensure_semantic_bridge_folder()
    names: List[str] = []
    if root:
        try:
            os.makedirs(root, exist_ok=True)
        except OSError:
            pass
        for ext in ("*.safetensors", "*.pt", "*.pth"):
            names.extend(os.path.basename(p) for p in glob.glob(os.path.join(root, ext)))
        try:
            import folder_paths
            names.extend(folder_paths.get_filename_list(SEMANTIC_BRIDGE_FOLDER) or [])
        except Exception:
            pass
    out = sorted({n for n in names if n and not n.startswith("(")})
    return out or [MISSING_ADAPTER_LABEL]


def resolve_semantic_bridge_path(filename: str) -> Optional[str]:
    name = str(filename or "").strip()
    if not name or name.startswith("("):
        return None
    if os.path.isabs(name) and os.path.isfile(name):
        return name
    try:
        import folder_paths
        ensure_semantic_bridge_folder()
        path = folder_paths.get_full_path(SEMANTIC_BRIDGE_FOLDER, name)
        if path and os.path.isfile(path):
            return path
    except Exception:
        pass
    root = ensure_semantic_bridge_folder()
    if root:
        candidate = os.path.join(root, name)
        if os.path.isfile(candidate):
            return candidate
    return None


def load_semantic_student(path: str) -> SemanticStudent:
    cached = _MODEL_CACHE.get(path)
    if cached is not None:
        return cached
    student = SemanticStudent()
    if path.endswith(".safetensors"):
        from safetensors.torch import load_file
        state_dict = load_file(path)
    else:
        try:
            blob = torch.load(path, map_location="cpu", weights_only=True)
        except TypeError:
            blob = torch.load(path, map_location="cpu")
        state_dict = blob.get("state_dict", blob) if isinstance(blob, dict) else blob

    student.load_state_dict(state_dict, strict=False)
    student.eval()
    _MODEL_CACHE[path] = student
    return student


def apply_semantic_bridge(
    conditioning: List[Any],
    pack: Optional[Dict[str, Any]],
    task_key: str = "fl2va",
) -> List[Any]:
    """Rewrites the text conditioning tokens using the Semantic Bridge student MLP."""
    if not pack or not conditioning:
        return conditioning

    adapter = pack.get("adapter")
    path = resolve_semantic_bridge_path(adapter)
    if not path or not os.path.isfile(path):
        return conditioning

    alpha = float(pack.get("alpha", DEFAULT_ALPHA))
    magnitude_match = bool(pack.get("magnitude_match", True))

    try:
        student = load_semantic_student(path)
        out_cond = []
        for emb, meta in conditioning:
            if not torch.is_tensor(emb):
                out_cond.append([emb, meta])
                continue

            orig_device = emb.device
            orig_dtype = emb.dtype

            H = emb.float()
            student = student.to(H.device)

            with torch.no_grad():
                # RMS norm
                rms = torch.rsqrt(H.pow(2).mean(dim=-1, keepdim=True) + 1e-6)
                x = H * rms
                S = student(x)

                if magnitude_match:
                    norm_h = torch.norm(H, dim=-1, keepdim=True) + 1e-6
                    norm_s = torch.norm(S, dim=-1, keepdim=True) + 1e-6
                    S = S * (norm_h / norm_s)

                C = H + alpha * (S - H)
                C = C.to(device=orig_device, dtype=orig_dtype)

            new_meta = dict(meta)
            new_meta["mmx_semantic_bridge"] = True
            out_cond.append([C, new_meta])

        return out_cond
    except Exception as exc:
        log.warning(f"Semantic Bridge rewrite skipped: {exc}")
        return conditioning


class MiniMaxH3DirectorSemanticBridge:
    """Pack Semantic Bridge settings to rewrite conditioning tokens with student MLP."""

    @classmethod
    def INPUT_TYPES(cls):
        adapters = list_semantic_bridge_adapters()
        default_adapter = adapters[0] if adapters else ""
        return {
            "required": {
                "adapter": (
                    adapters,
                    {
                        "default": default_adapter,
                        "tooltip": "Student MLP weights (~11MB) in ComfyUI/models/semantic_bridge/.",
                    },
                ),
                "alpha": (
                    "FLOAT",
                    {
                        "default": DEFAULT_ALPHA,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.01,
                        "tooltip": "Residual mix strength: C = H + alpha * (S' - H). Default 0.15.",
                    },
                ),
                "magnitude_match": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Match student output vector magnitude to original hidden state.",
                    },
                ),
            },
        }

    RETURN_TYPES = (MMX_DIR_SEMANTIC_BRIDGE,)
    RETURN_NAMES = ("semantic_bridge",)
    FUNCTION = "pack"
    CATEGORY = "ComfyUI-AhmedAhmedEG"
    DESCRIPTION = (
        "Connect to Director.semantic_bridge. Rewrites official cond tokens with the "
        "Semantic Bridge student MLP. Unconnected Director is identical."
    )

    def pack(self, adapter, alpha=DEFAULT_ALPHA, magnitude_match=True, **kwargs):
        return (
            {
                "adapter": adapter,
                "alpha": alpha,
                "magnitude_match": magnitude_match,
            },
        )
