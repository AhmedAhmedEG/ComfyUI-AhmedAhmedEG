"""Cached-shot player with demand-driven frames/audio/FPS for post-processing."""
import json


class MiniMaxH3SmartPreview:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"project_state": ("STRING", {"forceInput": True,
            "tooltip": "Connect the Master's project_state output. Reads completed shot caches without exporting the full movie."})},
            "optional":{"preview_settings":('STRING',{'default':'{}','multiline':False})},
            "hidden":{"prompt":"PROMPT","unique_id":"UNIQUE_ID"}}

    RETURN_TYPES = ('IMAGE','AUDIO','FLOAT')
    RETURN_NAMES = ('images','audio','fps')
    FUNCTION = "preview"
    OUTPUT_NODE = True
    CATEGORY = "ComfyUI-AhmedAhmedEG/Output"

    def preview(self, project_state, preview_settings='{}',prompt=None,unique_id=None):
        state = json.loads(project_state)
        if not isinstance(state, dict) or not state.get("project_id") or not isinstance(state.get("clips"), list):
            raise ValueError("Smart Preview needs the Master's project_state output.")
        try:
            from ..core.progress import accept_preview_input
        except ImportError:
            from core.progress import accept_preview_input
        accept_preview_input(state)
        outputs=(None,None,24.0)
        # Merely watching a preview must not assemble an entire raw movie.
        linked={link[1] for node in (prompt or {}).values() for link in node.get('inputs',{}).values()
            if isinstance(link,(list,tuple)) and len(link)==2 and str(link[0])==str(unique_id) and link[1] in (0,1,2)}
        if linked & {0,1}:
            try:
                from ..core.preview_outputs import load_preview_outputs
            except ImportError:
                from core.preview_outputs import load_preview_outputs
            options=json.loads(preview_settings or '{}')
            outputs=load_preview_outputs(state,options.get('scope','latest'),options.get('quality','original'),options.get('stream','final'),want_images=0 in linked)
        return {"ui": {"mmx_project": [json.dumps(state, ensure_ascii=False)]}, "result": outputs}
