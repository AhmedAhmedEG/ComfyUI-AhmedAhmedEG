"""MiniMax canvas-grid helpers selected from AIMixer."""


from __future__ import annotations


MINIMAX_CANVAS_STRIDE = 32


def snap_dimension(value: int, stride: int = MINIMAX_CANVAS_STRIDE) -> int:
    """Round *value* to the nearest multiple of *stride*, keeping at least *stride*."""
    return max(stride, round(value / stride) * stride)


def ensure_minimax_canvas(width: int, height: int) -> tuple[int, int]:
    """Snap width/height to MiniMax H3 canvas multiples (32)."""
    return snap_dimension(int(width)), snap_dimension(int(height))
