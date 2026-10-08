"""Authoring updates identify the actual shot completed by this execution."""
import logging


def shot_event(node_id, project_id, clip_id, phase, **data):
    try:
        from server import PromptServer
        if PromptServer.instance is not None:
            PromptServer.instance.send_sync("minimax_director/shot", {"node": str(node_id),
                "project_id": project_id, "clip_id": clip_id, "phase": phase, **data})
    except ImportError:
        pass
    except Exception as exc:
        logging.getLogger("MiniMaxH3.progress").debug("UI event unavailable: %s", exc)
