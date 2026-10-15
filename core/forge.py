"""Prompt drafts retain source context and require explicit review/apply."""
from __future__ import annotations
import copy
import hashlib
import json
import math
import urllib.request
import uuid
from .project import migrate_timeline


def reference_context(timeline):
    """Include real pool metadata without embedding tensors or preview URLs."""
    rows = {}
    for source in (timeline.get("references", []), timeline.get("available_refs", [])):
        for row in source:
            if not isinstance(row, dict) or not row.get("id"):
                continue
            rows[row["id"]] = {key: row.get(key) for key in
                ("id", "type", "name", "role", "description", "filename", "subfolder", "folder_type", "characters", "position", "retention", "forge_include")}
    return list(rows.values())


def context_key(timeline):
    value = copy.deepcopy(timeline)
    value.pop("available_refs", None)
    value["reference_context"] = reference_context(timeline)
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def parse_draft(text, count):
    text = str(text).strip()
    if text.startswith("```"):
        text = "\n".join(text.splitlines()[1:-1])
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Prompt provider must return a JSON object with a shots array.") from exc
    shots = data.get("shots") if isinstance(data, dict) else None
    if not isinstance(shots, list) or len(shots) != count:
        raise ValueError(f"Expected exactly {count} drafted shots.")
    for shot in shots:
        if not isinstance(shot, dict) or not isinstance(shot.get("prompt"), str) or not shot["prompt"].strip():
            raise ValueError("Every drafted shot must contain a non-empty prompt.")
        duration = float(shot.get("duration", 5))
        if not math.isfinite(duration) or duration <= 0 or duration > 150:
            raise ValueError("Draft duration must be between zero and 150 seconds.")
        # A model drafts authoring fields; it cannot mark a take validated,
        # replace assets, select arbitrary checkpoints, or unlock source clips.
        unknown = set(shot) - {"prompt", "duration", "type"}
        if unknown:
            raise ValueError(f"Unsupported drafted fields: {', '.join(sorted(unknown))}")
        from .task_modes import normalize_mode
        shot["type"] = normalize_mode(shot.get("type", "T2V"))
        shot["duration"] = duration
    return shots


def draft_prompts(timeline, instruction, count=1, backend="ollama", endpoint="http://localhost:11434",
                  model="", api_key="", generator=None, images=None, creativity=4, detail=6, shot_descriptions=None, continuation_clip_id="", job=None):
    count = int(count)
    if not 1 <= count <= 100: raise ValueError("Draft shot count must be between 1 and 100.")
    creativity,detail=int(creativity),int(detail)
    if not 1<=creativity<=10 or not 1<=detail<=10: raise ValueError("Creativity and Detail must be between 1 and 10.")
    state = migrate_timeline(timeline)
    from .forge_cast import clip_bindings, compile_cast_prompt
    bindings=[clip_bindings(state,row) for row in state.get('clips',[])]
    if continuation_clip_id:
        start=next((i for i,row in enumerate(state['clips']) if row.get('id')==continuation_clip_id),-1)
        if start<=0:raise ValueError('Choose a continuation clip with a predecessor.')
        bindings=bindings[start:]
    refs = [row for row in reference_context(state) if row.get('forge_include') is not False]
    refs.extend({"id": f"RefMod {row.get('slot')}", "type": "refmod", "description": row.get("description", "")} for row in state.get("refmods", []) if row.get("enabled", True))
    system = ("Draft MiniMax H3 video shots. Return only JSON: {\"shots\":[{\"prompt\":\"...\",\"duration\":5,\"type\":\"T2V\"}]}. "
        "Preserve identities, reference descriptions, existing context and requested retention. "
        "Use the given reference IDs; do not invent references. Describe visual action, camera, soundscape and music. "
        f"Produce exactly {count} shots. Reference context: {json.dumps(refs, ensure_ascii=False)}")
    system += f" Creativity={creativity}/10; detail={detail}/10. Detail adds descriptive precision, never extra shots. Keep continuous action when asked; do not invent cuts or unsolicited music. Output canvas: {state.get('resolution',{})}."
    system += ' Clip-local native labels and cast assignments: '+json.dumps(bindings,ensure_ascii=False)+'. Use these labels exactly; do not invent or renumber subjects. Return action/camera/audio prose in prompt; subject and retention headers are compiled from the reviewed cast metadata.'
    if shot_descriptions:
        system += " Shot instructions: " + json.dumps(list(shot_descriptions)[:count],ensure_ascii=False)
    user = str(instruction) + "\nShared prompt:\n" + str(state.get("shared_prompt", "")) + "\nExisting timeline:\n" + json.dumps(state.get("clips", []), ensure_ascii=False)
    continuation_key=None
    if continuation_clip_id:
        from .forge_context import predecessor_context
        frames,continuation_key=predecessor_context(state,continuation_clip_id)
        import base64,io
        from PIL import Image
        tail=[]
        for pixels in frames:
            image=Image.fromarray((pixels.cpu().clamp(0,1).numpy()*255).round().astype('uint8'));image.thumbnail((1024,1024))
            blob=io.BytesIO();image.save(blob,format='PNG');tail.append(base64.b64encode(blob.getvalue()).decode())
        images=[*(images or []),*tail]
        system+=f' The final {len(tail)} attached pictures are chronological previous-clip tail frames, not native reference slots. Continue their motion into clip {continuation_clip_id}; do not label them Picture references.'
    if backend == "local":
        if not callable(generator): raise ValueError("Local Prompt Forge requires a connected callable language-model pipeline.")
        options = {"max_new_tokens": min(32768, max(2048, count*256)), "temperature":creativity/10}
        if images: options["images"] = images
        if job:
            job.check()
            if getattr(generator,'supports_cancel',False):options['job']=job
        response = generator([{"role": "system", "content": system}, {"role": "user", "content": user}], **options)
        text = response[0]["generated_text"] if isinstance(response, list) else response
        if isinstance(text, list): text = text[-1]["content"]
    else:
        if backend not in ("ollama", "compatible"):
            raise ValueError("Prompt backend must be local, ollama or compatible.")
        if not endpoint.startswith(("http://", "https://")) or not model:
            raise ValueError("Prompt Forge needs an HTTP endpoint and model name.")
        content = user
        if images and backend == "compatible":
            content = [{"type": "text", "text": user}, *[{"type": "image_url", "image_url": {"url": "data:image/png;base64," + image}} for image in images]]
        messages = [{"role": "system", "content": system}, {"role": "user", "content": content}]
        if images and backend == "ollama": messages[-1]["images"] = images
        payload = {"model": model, "messages": messages, "stream": bool(job), **({"options":{"temperature":creativity/10},"keep_alive":0} if backend=="ollama" else {"temperature":creativity/10})}
        suffix = "/api/chat" if backend == "ollama" else "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key: headers["Authorization"] = "Bearer " + api_key
        request = urllib.request.Request(endpoint.rstrip("/") + suffix, data=json.dumps(payload).encode(), headers=headers)
        with urllib.request.urlopen(request, timeout=180) as response:
            if job:
                job.bind_response(response);job.check();parts=[]
                try:
                    for line in response:
                        job.check();line=line.decode('utf-8').strip()
                        if not line or line.startswith(':'):continue
                        if backend=='compatible':
                            if not line.startswith('data:'):continue
                            line=line[5:].strip()
                            if line=='[DONE]':break
                        row=json.loads(line)
                        parts.append(row.get('message',{}).get('content','') if backend=='ollama' else (row.get('choices') or [{}])[0].get('delta',{}).get('content') or '')
                except (OSError,ValueError):
                    job.check()
                    raise
                text=''.join(parts)
            else:
                result=json.load(response)
                text=result['message']['content'] if backend=='ollama' else result['choices'][0]['message']['content']
    if job:job.check()
    shots=parse_draft(text,count)
    for index,shot in enumerate(shots):
        if index<len(bindings):shot['prompt']=compile_cast_prompt(shot['prompt'],bindings[index])
    return {"context_key": context_key(timeline), "shots": shots, "count": count,
        "reference_bindings":bindings[:count],
        "continuation_clip_id":continuation_clip_id,"continuation_key":continuation_key}


def apply_draft(timeline, draft, policy="replace"):
    if draft.get('continuation_clip_id'):
        from .forge_context import predecessor_context
        _,key=predecessor_context(timeline,draft['continuation_clip_id'],False)
        if key!=draft.get('continuation_key'):raise ValueError('The predecessor take changed; regenerate the continuation draft.')
    if draft.get("context_key") != context_key(timeline):
        raise ValueError("Timeline context changed; regenerate or review a fresh draft before applying.")
    if policy not in ("replace", "append"):
        raise ValueError("Draft apply policy must be replace or append.")
    shots = parse_draft(json.dumps({"shots": draft.get("shots")}), int(draft.get("count", 0)))
    state = migrate_timeline(timeline)
    from .task_modes import normalize_mode
    old = state["clips"]
    start=next((i for i,row in enumerate(old) if row.get('id')==draft.get('continuation_clip_id')),0) if draft.get('continuation_clip_id') else 0
    created = []
    for index, proposed in enumerate(shots):
        # Existing references and overrides survive replacing a prompt draft.
        base = copy.deepcopy(old[start+index]) if policy == "replace" and start+index < len(old) else {}
        if policy=='append' and old:
            source=old[min(start+index,len(old)-1)]
            base={key:copy.deepcopy(source[key]) for key in ('ref_ids','audio_mode','continuity_mode','context_length','audio_context_length') if key in source}
        if policy=='replace' and base and proposed["type"] != normalize_mode(base.get("type","T2V")):
            raise ValueError("A draft cannot change an existing clip type. Append new clips instead.")
        base.update(proposed)
        base.setdefault("id", "clip_" + uuid.uuid4().hex)
        base.setdefault("name", f"Shot {index+1}")
        base.setdefault("selected", False)
        base["validated"] = False
        from .forge_mapping import prompt_digest
        snapshot=draft.get('reference_bindings',[])
        base['forge_reference_snapshot']=snapshot[index] if index<len(snapshot) else []
        base['forge_prompt_digest']=prompt_digest(base['prompt'])
        created.append(base)
    state["clips"] = [*old, *created] if policy == "append" else [*old[:start],*created,*old[start+len(created):]] if draft.get('continuation_clip_id') else created
    return state
