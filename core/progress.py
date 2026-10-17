"""Authoring updates identify the actual shot completed by this execution."""
import logging
import json
import threading
from collections import OrderedDict

_states = OrderedDict()
_lock = threading.Lock()
_sequence = 0


def current_clip_progress(node_id, project_id):
    """Small read-only snapshot for clients that miss a websocket transition."""
    with _lock:
        value = _states.get((str(node_id), str(project_id)))
        if value is None:
            # Subgraph execution prefixes UNIQUE_ID; the editor has the local ID.
            matches = [state for (node, project), state in _states.items()
                       if project == str(project_id) and node.rsplit(':', 1)[-1] == str(node_id)]
            value = matches[0] if len(matches) == 1 else None
        return dict(value) if value else None


def progress_snapshot(node_id, project_id, queue):
    state = current_clip_progress(node_id, project_id)
    running, _ = queue.get_current_queue()
    active = bool(state and state.get('prompt_id') in {item[1] for item in running})
    return {'state': state, 'active': active}


def preview_run_context(project_id, shots, queue, stream='final'):
    """Hide only takes scheduled for replacement; admit each completion live."""
    running, pending = queue.get_current_queue()
    blocked = set()
    matched_prompt = None
    with _lock:
        states = [dict(state) for (_, project), state in _states.items()
                  if project == str(project_id)]
    for item in [*running, *pending]:
        for node_id, node in item[2].items():
            if node.get('class_type') not in ('MiniMaxH3MasterNode', 'MiniMaxH3MasterDirector'):
                continue
            inputs = node.get('inputs', {})
            try:
                submitted = json.loads(inputs.get('timeline_data') or '{}')
            except (ValueError, TypeError):
                continue
            if str(submitted.get('project_id') or node_id) != str(project_id):
                continue
            matched_prompt = item[1]
            authored = submitted.get('clips', shots)
            mode = inputs.get('generation_mode', submitted.get('generation_mode', 'Next clip'))
            if mode == 'Conditioning only':
                continue
            # These submitted flags describe what Master actually scheduled.
            # Current editor approval changes never hide idle saved footage or
            # expose an old take while its replacement is still being sampled.
            candidates = [s['id'] for s in authored if not s.get('validated') and not s.get('locked')]
            scheduled = set(candidates if mode in ('All clips', 'All shots') else candidates[:1])
            if item in running:
                matches = [state for state in states if state.get('prompt_id') == item[1]
                           and str(state.get('node')).rsplit(':', 1)[-1] == str(node_id).rsplit(':', 1)[-1]]
                if matches:
                    state = max(matches, key=lambda value: value['sequence'])
                    index = next((i for i, shot in enumerate(authored) if shot.get('id') == state.get('clip_id')), None)
                    if index is not None:
                        include_current = state['phase'] == 'completed' or (
                            state['phase'] == 'first_pass_ready' and stream == 'first_pass')
                        completed = {s['id'] for s in authored[:index + int(include_current)]}
                        scheduled -= completed
            blocked.update(scheduled)
    if matched_prompt is None:
        return None
    return {'prompt_id': matched_prompt,
            'clip_ids': [shot['id'] for shot in shots if shot['id'] not in blocked]}


def shot_event(node_id, project_id, clip_id, phase, **data):
    global _sequence
    prompt_id = None
    try:
        from server import PromptServer
        queue = getattr(PromptServer.instance, 'prompt_queue', None)
        if queue is not None:
            running, _ = queue.get_current_queue()
            if len(running) == 1:
                prompt_id = running[0][1]
    except (ImportError, AttributeError):
        pass
    with _lock:
        _sequence += 1
        event = {"node": str(node_id), "project_id": project_id,
                 "clip_id": clip_id, "phase": phase, **data, "sequence": _sequence,
                 "prompt_id": prompt_id}
        key = (str(node_id), str(project_id))
        if phase == "timeline_ready":
            _states.pop(key, None)
        else:
            _states[key] = event
            _states.move_to_end(key)
        while len(_states) > 64:
            _states.popitem(last=False)
    try:
        from server import PromptServer
        if PromptServer.instance is not None:
            PromptServer.instance.send_sync("minimax_director/shot", event)
    except ImportError:
        pass
    except Exception as exc:
        logging.getLogger("MiniMaxH3.progress").debug("UI event unavailable: %s", exc)
