"""Canonical prompt engineering, structuring, and alignment engine for MiniMax H3 Master Director."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .config import align_frame_count, FPS
from .refmod import translate_refmod_aliases

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


def format_timestamp(seconds: float) -> str:
    """Format seconds into MM:SS.mmm (e.g. 00:04.500)."""
    mins = int(seconds // 60)
    secs = seconds % 60
    return f"{mins:02d}:{secs:06.3f}"


def format_alignment_header(mode: str, duration_sec: float) -> str:
    """Generate the official canonical alignment header line for FL2VA/I2VA/L2VA."""
    aligned_frames = align_frame_count(int(duration_sec * FPS))
    snapped_sec = aligned_frames / FPS
    sec_str = f"{snapped_sec:.2f}"

    if mode == "I2VA":
        return (
            "For the target video, at 0.00 seconds into the target video, "
            "<Picture 1> (from [Shot 1]) is fully referenced."
        )
    elif mode == "FL2VA":
        return (
            "How the reference pictures align with the target video — "
            "Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; "
            f"Picture 2 (from Shot 1) aligns with the {sec_str}-second mark of the target video."
        )
    elif mode == "L2VA":
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
    header = ""
    if mode == "FL2VA" and has_first_frame and has_last_frame:
        header = format_alignment_header("FL2VA", duration_sec)
    elif mode == "I2VA" or (mode == "FL2VA" and has_first_frame and not has_last_frame):
        header = format_alignment_header("I2VA", duration_sec)
    elif mode == "L2VA" or (mode == "FL2VA" and not has_first_frame and has_last_frame):
        header = format_alignment_header("L2VA", duration_sec)

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


def prefill_ref2va_scaffold(
    image_count: int,
    video_count: int,
    audio_count: int,
    refmod_items: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, str]:
    """Generate initial template scaffolding for subject_definitions, summary, and retention."""
    defs: List[str] = []
    ret: List[str] = []
    subjects: List[str] = []

    # Images
    for i in range(1, image_count + 1):
        subj = f"<Subject {len(subjects) + 1}>"
        subjects.append(subj)
        defs.append(f"{subj} is the main subject in <Picture {i}>.")
        defs.append(f"<Picture {i}> defines the visual identity and appearance of {subj}.")
        ret.append(f"{subj}: fully_preserved - appearance and costume are maintained.")

    # Videos
    for i in range(1, video_count + 1):
        subj = f"<Subject {len(subjects) + 1}>"
        subjects.append(subj)
        defs.append(f"{subj} is the action and motion sequence seen in <Video {i}>.")
        defs.append(f"<Video {i}> provides the dynamic camera movement and motion rhythm.")
        ret.append(f"{subj}: attribute_transfer - motion pacing is transferred.")

    # Audios
    for i in range(1, audio_count + 1):
        defs.append(f"<Audio {i}> is the sound and voice reference.")
        ret.append(f"<Audio {i}>: reference - timbre and ambient acoustics are followed.")

    # RefMods
    if refmod_items:
        for item in refmod_items:
            slot = item["slot"]
            kind = item["kind"]
            name = item["name"]
            desc = item.get("description", "")
            subj = f"<Subject {len(subjects) + 1}>"
            subjects.append(subj)
            defs.append(f"<RefMod {slot}> ({name}) defines {subj}: {desc or 'custom saved identity'}.")
            ret.append(f"<RefMod {slot}>: fully_preserved - character attributes remain consistent.")

    summary_task = "[reference generation" + (" + audio reference]" if audio_count > 0 else "]")
    summary_line = f"{summary_task} Cinematic scene starring {', '.join(subjects[:2]) if subjects else 'the subjects'} with natural pacing."

    return {
        "subject_definitions": "\n".join(defs),
        "summary": summary_line,
        "retention_analysis": "\n".join(ret),
        "detailed_description": "[Shot 1] The scene opens with smooth camera movement capturing the environment in cinematic detail.",
        "overall_soundscape": "Natural environmental ambience and synchronized diegetic sounds.",
        "non_diegetic_music": "N/A",
    }
