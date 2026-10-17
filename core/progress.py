"""Authoring updates identify the actual shot completed by this execution."""
import logging
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
