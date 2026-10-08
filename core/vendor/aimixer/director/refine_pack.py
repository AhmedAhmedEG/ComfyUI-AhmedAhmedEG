"""External Refine pack for MiniMax H3 Director (graph-wired config).

Connect ``MiniMaxH3DirectorRefine.refine`` → ``MiniMaxH3Director.refine``.
Unconnected = current single-pass sampling.
"""


from __future__ import annotations


from typing import Any


HAILUO_REFINE_SIGMAS = (0.85, 0.7250, 0.4219, 0.0)


MAX_SPATIAL_TILES = 8


DEFAULT_SPATIAL_TILES = 2


DEFAULT_TILE_OVERLAP = 128


def parse_refine_sigmas(raw: Any, *, fallback: bool = False) -> tuple[float, ...]:
    """Parse ManualSigmas text or a BasicScheduler SIGMAS tensor."""
    vals: list[float] = []
    from_tensor = is_refine_sigmas_tensor(raw)
    if from_tensor:
        try:
            vals = [float(x) for x in raw.detach().float().cpu().reshape(-1).tolist()]
        except Exception:
            vals = []
    elif isinstance(raw, (list, tuple)):
        for part in raw:
            try:
                vals.append(float(part))
            except (TypeError, ValueError):
                continue
    else:
        text = str(raw or "").replace(";", ",").replace("\n", ",")
        for part in text.split(","):
            token = str(part).strip()
            if not token:
                continue
            try:
                vals.append(float(token))
            except (TypeError, ValueError):
                continue
    if len(vals) < 2:
        if not fallback:
            raise ValueError(
                "Refine SIGMAS 至少需要 2 个数（步数 + 结尾 0）。"
                "请检查 BasicScheduler 的 steps / denoise。"
            )
        return HAILUO_REFINE_SIGMAS
    if abs(vals[-1]) > 1e-8:
        vals.append(0.0)
    return tuple(vals)


def is_refine_sigmas_tensor(raw: Any) -> bool:
    return raw is not None and not isinstance(raw, (str, bytes, list, tuple)) and hasattr(raw, "reshape")


def resolve_latent_upscale_ref(raw: Any) -> tuple[Any, str]:
    """Return (loaded_module_or_None, filename)."""
    if raw is None or raw is False:
        return None, ""
    if isinstance(raw, str):
        name = raw.strip()
        return None, "" if name.startswith("(") else name
    if isinstance(raw, dict):
        name = str(raw.get("name") or raw.get("model_name") or "").strip()
        if name.startswith("("):
            name = ""
        return raw.get("model"), name
    name = str(getattr(raw, "name", None) or getattr(raw, "_h3_name", None) or "").strip()
    if hasattr(raw, "parameters") or hasattr(raw, "model"):
        return raw, name or type(raw).__name__
    return None, name
