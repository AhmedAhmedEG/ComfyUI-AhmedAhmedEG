"""Output sink for the separate, on-demand cached-shot player."""
import json


class MiniMaxH3SmartPreview:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"project_state": ("STRING", {"forceInput": True,
            "tooltip": "Connect the Master's project_state output. Reads completed shot caches without exporting the full movie."})}}

    RETURN_TYPES = ()
    FUNCTION = "preview"
    OUTPUT_NODE = True
    CATEGORY = "ComfyUI-AhmedAhmedEG/Output"

    def preview(self, project_state):
        state = json.loads(project_state)
        if not isinstance(state, dict) or not state.get("project_id") or not isinstance(state.get("clips"), list):
            raise ValueError("Smart Preview needs the Master's project_state output.")
        return {"ui": {"mmx_project": [json.dumps(state, ensure_ascii=False)]}, "result": ()}
