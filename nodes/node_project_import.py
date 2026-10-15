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
            'source':(['auto','current','dasiwa','aimixer','tritant'],)},
            'optional':{'restore_models':('BOOLEAN',{'default':False,'tooltip':'Load explicitly named installed diffusion checkpoints into the converted model pack. Missing or ambiguous bindings fail instead of substituting a different model.'})}}
    RETURN_TYPES=('MMX_TIMELINE','STRING','MMX_DIRECTOR_CONFIG','MMX_MODEL_PACK','MMX_REFMOD_LIBRARY')
    RETURN_NAMES=('timeline','conversion_report','config','model_pack','refmods')
    FUNCTION='convert'
    CATEGORY='ComfyUI-AhmedAhmedEG/Advanced graph tools'
    def convert(self,project_json,source='auto',restore_models=False):
        state,report=convert_project(json.loads(project_json),source)
        bindings=state.get('import_bindings',report['bindings'])
        try:
            from ..core.import_bindings import load_model_bindings
        except ImportError:
            from core.import_bindings import load_model_bindings
        models=load_model_bindings(bindings['model_bindings']) if restore_models else {}
        refmods={'refs':[{'id':r['id'],'type':'refmod','name':r['description'] or r['name'],'description':r['description'],'data':r['name'],'strength':r['strength']} for r in bindings['refmods'] if r['enabled']]}
        return state,json.dumps(report,ensure_ascii=False,indent=2),bindings['config'],models,refmods
