"""Persist and remap writer-produced ordinary media tags by stable asset ID."""
import hashlib,re

TAG=re.compile(r'<(Picture|Video|Audio)\s+(\d+)>')


def prompt_digest(prompt):return hashlib.sha256(prompt.encode()).hexdigest()


def mapped_prompt(clip,bindings):
    prompt=clip.get('prompt','');snapshot=clip.get('forge_reference_snapshot')
    if not snapshot or clip.get('forge_prompt_digest')!=prompt_digest(prompt):return prompt
    current={row['id']:row['label'] for row in bindings}
    old={row['label']:row['id'] for row in snapshot}
    def replace(match):
        label=f'<{match[1]} {int(match[2])}>'
        rid=old.get(label)
        if rid is None:return match[0]
        if rid not in current:raise ValueError('A verified prompt reference was removed. Review the clip prompt in Forge before generating.')
        return current[rid]
    return TAG.sub(replace,prompt)
