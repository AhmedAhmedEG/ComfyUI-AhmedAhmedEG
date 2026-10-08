"""Canonical prompt engineering, structuring, and alignment engine for MiniMax H3 Master Director."""

from __future__ import annotations

import re

from .config import align_frame_count, FPS

# Official MiniMax task types for summary section
TASK_TYPES = [
    "keyframe completion",
    "reference generation",
    "video editing",
    "video continuation",
    "audio reuse",
    "audio reference",
]

# Official retention markers
VISUAL_RETENTION_MARKERS = [
    "fully_preserved",
    "partially_preserved",
    "attribute_transfer",
    "weak_reference",
]
AUDIO_RETENTION_MARKERS = [
    "fully_copy",
    "partially_copy",
    "reference",
    "weak_reference",
]

MENTION_REGEX = re.compile(r"@\s*(Picture|Video|Audio|Subject)\s*(\d+)", re.I)
BRACKET_REGEX = re.compile(r"<\s*(Picture|Video|Audio|Subject)\s*(\d+)\s*>", re.I)


def clean_mentions(text: str) -> str:
    """Translate `@Picture 1` mentions and normalize brackets to standard `<Picture 1>` format."""
    if not isinstance(text, str):
        return ""
    # Normalize @mentions
    res = MENTION_REGEX.sub(lambda m: f"<{m.group(1).capitalize()} {m.group(2)}>", text)
    # Normalize bracketed tags
    res = BRACKET_REGEX.sub(lambda m: f"<{m.group(1).capitalize()} {m.group(2)}>", res)
    return res


def format_alignment_header(mode: str, duration_sec: float, has_first_frame: bool = True, has_last_frame: bool = True) -> str:
    """Generate the official canonical alignment header line for FL2VA/I2VA/L2VA."""
    aligned_frames = align_frame_count(int(duration_sec * FPS))
    snapped_sec = aligned_frames / FPS
    sec_str = f"{snapped_sec:.2f}"

    if mode == "I2VA" and has_first_frame:
        return (
            "For the target video, at 0.00 seconds into the target video, "
            "<Picture 1> (from [Shot 1]) is fully referenced."
        )
    elif mode == "FL2VA" and has_first_frame and has_last_frame:
        return (
            "How the reference pictures align with the target video — "
            "Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; "
            f"Picture 2 (from Shot 1) aligns with the {sec_str}-second mark of the target video."
        )
    elif mode == "L2VA" and has_last_frame:
        return (
            "How the reference pictures align with the target video — "
            f"<Picture 1> (from [Shot 1]) aligns with the {sec_str}-second mark of the target video."
        )
    return ""


def build_keyframe_mode_prompt(
    mode: str,
    imd: str,
    soundscape: str = "",
    music: str = "",
    duration_sec: float = 5.0,
    has_first_frame: bool = False,
    has_last_frame: bool = False,
    prompt_mode: str = "structured",
) -> str:
    """Assemble prompt for T2VA, I2VA, FL2VA, L2VA with exact official alignment lines."""
    imd_clean = clean_mentions(str(imd or "")).strip()
    sound_clean = clean_mentions(str(soundscape or "")).strip()
    music_clean = clean_mentions(str(music or "")).strip() or "N/A"

    if prompt_mode == "simple":
        # Flat unsectioned rendering
        lines = []
        if imd_clean:
            lines.append(f"integrated_multimodal_description: {imd_clean}")
        if sound_clean:
            lines.append(f"overall_soundscape: {sound_clean}")
        if music_clean and music_clean != "N/A":
            lines.append(f"non_diegetic_music: {music_clean}")
        return "\n\n".join(lines) if lines else imd_clean

    # Determine alignment header
    header = format_alignment_header(mode, duration_sec, has_first_frame, has_last_frame)

    body = (
        f"integrated_multimodal_description: {imd_clean}\n\n"
        f"overall_soundscape: {sound_clean}\n\n"
        f"non_diegetic_music: {music_clean}"
    )

    return f"{header}\n\n{body}".strip() if header else body.strip()


def build_ref2va_prompt(
    subject_definitions: str = "",
    summary: str = "",
    retention_analysis: str = "",
    detailed_description: str = "",
    soundscape: str = "",
    music: str = "",
    prompt_mode: str = "structured",
) -> str:
    """Assemble official 6-section REF2VA prompt."""
    s_defs = clean_mentions(str(subject_definitions or "")).strip()
    s_sum = clean_mentions(str(summary or "")).strip()
    s_ret = clean_mentions(str(retention_analysis or "")).strip()
    s_desc = clean_mentions(str(detailed_description or "")).strip()
    s_sound = clean_mentions(str(soundscape or "")).strip()
    s_music = clean_mentions(str(music or "")).strip() or "N/A"

    if prompt_mode == "simple":
        # Flat format
        sections = [
            ("subject_definitions", s_defs),
            ("summary", s_sum),
            ("retention_analysis", s_ret),
            ("detailed_description", s_desc),
            ("overall_soundscape", s_sound),
            ("non_diegetic_music", s_music),
        ]
        return "\n\n".join(f"{h}:\n{val}" for h, val in sections if val).strip()

    return (
        f"subject_definitions:\n{s_defs}\n\n"
        f"summary:\n{s_sum}\n\n"
        f"retention_analysis:\n{s_ret}\n\n"
        f"detailed_description:\n{s_desc}\n\n"
        f"overall_soundscape:\n{s_sound}\n\n"
        f"non_diegetic_music:\n{s_music}"
    ).strip()
