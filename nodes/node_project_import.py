"""Reviewed upstream metadata enters the same typed timeline boundary."""
import json
try:
    from ..core.project_conversion import convert_project
except ImportError:
    from core.project_conversion import convert_project

class MiniMaxH3ProjectImport:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'project_json':('STRING',{'default':'{}','multiline':True}),
            'source':(['auto','current','dasiwa','aimixer','tritant'],)}}
    RETURN_TYPES=('MMX_TIMELINE','STRING')
    RETURN_NAMES=('timeline','conversion_report')
    FUNCTION='convert'
    CATEGORY='ComfyUI-AhmedAhmedEG/Advanced graph tools'
    def convert(self,project_json,source='auto'):
        state,report=convert_project(json.loads(project_json),source)
        return state,json.dumps(report,ensure_ascii=False,indent=2)
