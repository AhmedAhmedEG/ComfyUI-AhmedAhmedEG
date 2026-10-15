"""Mode-specific writing contracts; video model routing remains in task_modes."""
from .task_modes import normalize_mode

RULES = {
    'T2VA': 'Write a self-contained scene. Do not invent reference tags or image endpoints.',
    'I2VA': 'The selected opening frame fixes the initial appearance and composition. Describe continuous motion away from it; use reviewed cast appearances as prose, without REF2VA subject headers or Picture tags.',
    'L2VA': 'The selected closing frame fixes the ending. Describe action and camera movement that arrive there, without inventing an opening-frame constraint or Picture tags.',
    'FL2VA': 'Respect both selected endpoints. Describe one continuous transition from the opening composition to the closing composition; avoid cuts. Use cast appearances as prose, without REF2VA subject headers or Picture tags.',
    'REF2VA': 'Use only the supplied clip-local Picture/Video/Audio labels. Reviewed cast cards define appearance. Write action, camera and audio prose; the compiler adds subject and retention definitions.',
    'V2V': 'Use the selected source video as motion/edit guidance. Describe the intended transformation and preserve unaffected motion. Only use supplied native reference labels.',
    'RV2V': 'Describe the source-video edit and the role of the selected image/audio references. Use only supplied clip-local labels and preserve unaffected source content.',
    'Image Inpaint': 'Describe the requested still-image edit. The output is one image from a five-frame native pass; do not invent a video sequence, camera travel or an audio scene.',
}


def writing_contracts(clips):
    return [{'clip_id': clip.get('id'), 'type': normalize_mode(clip.get('type', 'T2VA')),
             'rules': RULES[normalize_mode(clip.get('type', 'T2VA'))]} for clip in clips]


def uses_reference_headers(mode):
    return normalize_mode(mode) in ('REF2VA', 'V2V', 'RV2V')
