"""External groups connect through one canonical timeline socket."""
from .node_groups import _normalize_group
try:
    from ..core.timeline_input import groups_to_timeline
    from ..core.project import export_timeline_state
except ImportError:
    from core.timeline_input import groups_to_timeline
    from core.project import export_timeline_state
import json


class MiniMaxH3TimelineBuilder:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'groups':('MMX_DIR_GROUP',)},'hidden':{'unique_id':'UNIQUE_ID'}}
    RETURN_TYPES=('MMX_TIMELINE','STRING')
    RETURN_NAMES=('timeline','authoring_json')
    FUNCTION='build'
    CATEGORY='ComfyUI-AhmedAhmedEG/Advanced graph tools'
    def build(self, groups, unique_id='builder'):
        state=groups_to_timeline(_normalize_group(groups),str(unique_id))
        return state,json.dumps(export_timeline_state(state),ensure_ascii=False)
