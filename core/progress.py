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
    """Limit live previews to the processed prefix, never old future takes."""
    running, pending = queue.get_current_queue()
    approved = {shot['id'] for shot in shots if shot.get('validated') or shot.get('locked')}
    pending_regeneration = set()
    # Use submitted approvals as well as the live editor. Checking a box after
    # enqueue cannot turn a scheduled regeneration into a reusable old take.
    for item in [*running, *pending]:
        for node_id, node in item[2].items():
            if node.get('class_type') not in ('MiniMaxH3MasterNode', 'MiniMaxH3MasterDirector'):
                continue
            try:
                submitted = json.loads(node.get('inputs', {}).get('timeline_data') or '{}')
            except (ValueError, TypeError):
                continue
            if str(submitted.get('project_id') or node_id) == str(project_id) and 'clips' in submitted:
                approved &= {s['id'] for s in submitted['clips'] if s.get('validated') or s.get('locked')}
                if item in pending:
                    candidates = [s['id'] for s in submitted['clips'] if not s.get('validated') and not s.get('locked')]
                    mode = node.get('inputs', {}).get('generation_mode', submitted.get('generation_mode', 'Next clip'))
                    if mode not in ('Conditioning only',):
                        pending_regeneration.update(candidates if mode in ('All clips', 'All shots') else candidates[:1])
    prompt_ids = {item[1] for item in running}
    with _lock:
        matches = [dict(state) for (_, project), state in _states.items()
                   if project == str(project_id) and state.get('prompt_id') in prompt_ids]
    if matches:
        state = max(matches, key=lambda item: item['sequence'])
        index = next((i for i, shot in enumerate(shots) if shot.get('id') == state.get('clip_id')), None)
        if index is None:
            return {'prompt_id': state['prompt_id'], 'clip_ids': []}
        include_current = state['phase'] == 'completed' or (
            state['phase'] == 'first_pass_ready' and stream == 'first_pass')
        return {'prompt_id': state['prompt_id'],
                'clip_ids': [shot['id'] for shot in shots if shot['id'] not in pending_regeneration and (shot['id'] in approved or
                             shot in shots[:index + int(include_current)])]}
    # A queued graph can be loading models before Master emits its first event.
    # Do not show the previous run's movie during that interval either.
    for item in [*running, *pending]:
        for node_id, node in item[2].items():
            if node.get('class_type') not in ('MiniMaxH3MasterNode', 'MiniMaxH3MasterDirector'):
                continue
            try:
                timeline = json.loads(node.get('inputs', {}).get('timeline_data') or '{}')
            except (ValueError, TypeError):
                continue
            if str(timeline.get('project_id') or node_id) == str(project_id):
                return {'prompt_id': item[1], 'clip_ids': [shot['id'] for shot in shots if shot['id'] in approved]}
    return None


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
