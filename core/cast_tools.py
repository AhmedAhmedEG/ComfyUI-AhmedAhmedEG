"""Reviewed people boxes and cast cards shared by the pack, Forge and imports."""
import base64
import io
import json
import math
import re

MAX_PEOPLE = 32


def boxes_of(raw):
    if raw is None:
        return []
    if not isinstance(raw, list) or len(raw) > MAX_PEOPLE:
        raise ValueError('People boxes must be a list of at most 32 people.')
    result, seen = [], set()
    for row in raw:
        if not isinstance(row,dict):raise ValueError('Each people box must be an object.')
        number = row.get('n')
        box = row.get('box')
        if isinstance(number, bool) or not isinstance(number, int) or not 1 <= number <= 99 or number in seen:
            raise ValueError('Each person needs a distinct character number from 1 to 99.')
        if not isinstance(box, list) or len(box) != 4 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in box):
            raise ValueError('People boxes use four finite coordinates between zero and one.')
        x1, y1, x2, y2 = map(float, box)
        if x2 - x1 < .02 or y2 - y1 < .02:
            raise ValueError('People boxes must have positive width and height of at least 2%.')
        seen.add(number)
        result.append({'n': number, 'box': [x1, y1, x2, y2], 'label': str(row.get('label', ''))[:200]})
    return result


def crop_for(boxes, number):
    """Use whole-frame position when a crop would contain another person."""
    own = next((r['box'] for r in boxes if r['n'] == number), None)
    if own is None:
        return None
    def area(b):
        return (b[2]-b[0])*(b[3]-b[1])
    for row in boxes:
        other = row['box']
        if row['n'] == number:
            continue
        overlap = max(0, min(own[2], other[2])-max(own[0], other[0])) * max(0, min(own[3], other[3])-max(own[1], other[1]))
        if overlap / min(area(own), area(other)) > .35:
            return None
    return own


def parse_people(text):
    text = str(text).strip()
    if text.startswith('```'):
        text = '\n'.join(text.splitlines()[1:-1])
    data = json.loads(text)
    people = data.get('people') if isinstance(data, dict) else data
    if not isinstance(people, list) or len(people) > MAX_PEOPLE:
        raise ValueError('The reader must return a people array with at most 32 entries.')
    rows = []
    for index, row in enumerate(people):
        box = row.get('box', row.get('bbox_2d'))
        if isinstance(box, list) and 'bbox_2d' in row:
            box = [float(v)/1000 for v in box]
        rows.append({'n': index+1, 'box': box, 'label': row.get('label', '')})
    rows = sorted(boxes_of(rows), key=lambda r: r['box'][0]+r['box'][2])
    return [{**r, 'n': i+1} for i, r in enumerate(rows)]


def cast_cards(raw):
    if raw is None:
        return {}
    if not isinstance(raw, dict) or len(raw) > 100:
        raise ValueError('Cast cards must be a small dictionary.')
    result = {}
    for key, value in raw.items():
        key = str(key)
        if not re.fullmatch(r'(?:[1-9]\d?|place|style|pose:[\w.-]{1,160})', key):
            raise ValueError('Invalid cast card identity.')
        if not isinstance(value, str) or len(value) > 4000:
            raise ValueError('Cast descriptions must be text of at most 4000 characters.')
        if value.strip():
            result[key] = value.strip()
    return result


def image_b64(image, crop=None):
    if crop:
        w, h = image.size
        x1, y1, x2, y2 = crop
        image = image.crop((max(0, int((x1-.02)*w)), max(0, int((y1-.02)*h)), min(w, math.ceil((x2+.02)*w)), min(h, math.ceil((y2+.02)*h))))
    image.thumbnail((1024, 1024))
    stream = io.BytesIO()
    image.convert('RGB').save(stream, format='PNG')
    return base64.b64encode(stream.getvalue()).decode()


def read_cast(timeline, key, load_image, provider, instruction=''):
    """One vision call per reviewed card; input selection never changes H3 refs."""
    key = str(key)
    cast_cards({key: 'validate'})
    pool = {r['id']: r for r in [*timeline.get('references', []), *timeline.get('available_refs', [])] if r.get('id')}
    selected = set(timeline.get('shared_ref_ids', [])) | {rid for clip in timeline.get('clips', []) for rid in clip.get('ref_ids', [])}
    pictures, notes = [], []
    for rid, row in pool.items():
        if rid not in selected or row.get('forge_include') is False or row.get('type') != 'image':
            continue
        boxes = boxes_of(row.get('boxes'))
        characters = [int(v) for v in row.get('characters', [])] if not isinstance(row.get('characters'), str) else [int(v.strip()) for v in row['characters'].split(',') if v.strip()]
        characters = list(dict.fromkeys([*characters, *[b['n'] for b in boxes]]))
        from .forge_cast import reference_roles
        roles = reference_roles(row)
        matches = int(key) in characters if key.isdigit() else key in roles if key in ('place', 'style') else 'pose' in roles and key == 'pose:'+rid
        if not matches:
            continue
        image = load_image(row)
        crop = crop_for(boxes, int(key)) if key.isdigit() else None
        position = next((b['box'] for b in boxes if str(b['n']) == key), None)
        pictures.append(image_b64(image, crop))
        notes.append({'reference': rid, 'cropped': bool(crop), 'person_box_in_full_frame': position if not crop else None, 'position': row.get('position'), 'instructions': row.get('description'), 'retention': row.get('retention', 'fully_preserved')})
    if not pictures:
        raise ValueError('Assign a matching image reference to a clip and set its character/role before reading this card.')
    if len(pictures) > 12:
        raise ValueError('Read a card from at most 12 selected reference pictures.')
    system = ('Describe only the requested character, place, style or pose from the attached pictures. '
              'Return concise appearance text only. For a character describe distinguishing face, hair, build, clothing and colours; '
              'for a pose describe stance only, without transferring identity. Respect the supplied retention policy and instructions. '
              'Cropped pictures target one person; do not describe others at the edges. For overlapping boxes, use the provided full-frame position. '
              'Do not invent invisible traits. User corrections override contradictory visible traits.')
    text = provider(system, json.dumps({'card': key, 'pictures': notes, 'corrections': str(instruction)[:4000]}, ensure_ascii=False), pictures)
    text = re.sub(r'<think>.*?</think>', '', str(text), flags=re.S).strip()
    if text.startswith('```'):
        text = '\n'.join(text.splitlines()[1:-1]).strip()
    if not text:raise ValueError('The vision reader returned an empty description.')
    return cast_cards({key: text})[key]
