"""Prompt drafts retain source context and require explicit review/apply."""
from __future__ import annotations
import copy
import hashlib
import json
import math
import urllib.request
import uuid
from .project import migrate_timeline


def context_key(timeline):
    value = copy.deepcopy(timeline)
    value.pop("available_refs", None)
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
                  model="", api_key="", generator=None, images=None):
    count = int(count)
    if not 1 <= count <= 100: raise ValueError("Draft shot count must be between 1 and 100.")
    state = migrate_timeline(timeline)
    refs = [{key: row.get(key) for key in ("id", "type", "role", "description")} for row in state.get("references", [])]
    refs.extend({"id": f"RefMod {row.get('slot')}", "type": "refmod", "description": row.get("description", "")} for row in state.get("refmods", []) if row.get("enabled", True))
    system = ("Draft MiniMax H3 video shots. Return only JSON: {\"shots\":[{\"prompt\":\"...\",\"duration\":5,\"type\":\"T2V\"}]}. "
        "Preserve identities, reference descriptions, existing context and requested retention. "
        "Use the given reference IDs; do not invent references. Describe visual action, camera, soundscape and music. "
        f"Produce exactly {count} shots. Reference context: {json.dumps(refs, ensure_ascii=False)}")
    user = str(instruction) + "\nShared prompt:\n" + str(state.get("shared_prompt", "")) + "\nExisting timeline:\n" + json.dumps(state.get("clips", []), ensure_ascii=False)
    if backend == "local":
        if not callable(generator): raise ValueError("Local Prompt Forge requires a connected callable language-model pipeline.")
        options = {"max_new_tokens": min(32768, max(2048, count*256))}
        if images: options["images"] = images
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
        payload = {"model": model, "messages": messages, "stream": False}
        suffix = "/api/chat" if backend == "ollama" else "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key: headers["Authorization"] = "Bearer " + api_key
        request = urllib.request.Request(endpoint.rstrip("/") + suffix, data=json.dumps(payload).encode(), headers=headers)
        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.load(response)
        text = result["message"]["content"] if backend == "ollama" else result["choices"][0]["message"]["content"]
    return {"context_key": context_key(timeline), "shots": parse_draft(text, count), "count": count}


def apply_draft(timeline, draft, policy="replace"):
    if draft.get("context_key") != context_key(timeline):
        raise ValueError("Timeline context changed; regenerate or review a fresh draft before applying.")
    if policy not in ("replace", "append"):
        raise ValueError("Draft apply policy must be replace or append.")
    shots = parse_draft(json.dumps({"shots": draft.get("shots")}), int(draft.get("count", 0)))
    state = migrate_timeline(timeline)
    old = state["clips"]
    created = []
    for index, proposed in enumerate(shots):
        # Existing references and overrides survive replacing a prompt draft.
        base = copy.deepcopy(old[index]) if policy == "replace" and index < len(old) else {}
        base.update(proposed)
        base.setdefault("id", "clip_" + uuid.uuid4().hex)
        base.setdefault("name", f"Shot {index+1}")
        base.setdefault("selected", True)
        base["validated"] = False
        created.append(base)
    state["clips"] = [*old, *created] if policy == "append" else created
    return state
