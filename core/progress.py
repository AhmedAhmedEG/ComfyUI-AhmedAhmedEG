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
        return dict(value) if value else None


def shot_event(node_id, project_id, clip_id, phase, **data):
    global _sequence
    with _lock:
        _sequence += 1
        event = {"node": str(node_id), "project_id": project_id,
                 "clip_id": clip_id, "phase": phase, **data, "sequence": _sequence}
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
