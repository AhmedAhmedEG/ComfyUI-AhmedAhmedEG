"""Shared refinement policy resolution, independent of authoring widgets."""
from .project import seed_string
from .resolution import plan_canvas

MAX_REFINE_PASSES = 9999


def next_refine_seed(value, policy):
    base=int(seed_string(value))
    if policy=='fixed':return str(base)
    if policy in ('increment','decrement'):return str((base+(1 if policy=='increment' else -1)) & ((1<<64)-1))
    if policy=='randomize':
        import secrets
        return str(secrets.randbits(64))
    raise ValueError('Unknown refinement seed advancement policy.')


def advance_refine_control(pack):
    if not pack or pack.get('seed_policy')!='independent' or not pack.get('owner_id'):return
    current=str(pack.get('refine_seed','0'));new=next_refine_seed(current,pack.get('seed_after_generate','fixed'))
    if new==current:return
    try:
        from server import PromptServer
        if getattr(PromptServer,'instance',None):
            PromptServer.instance.send_sync('minimax_refine_seed',{'node_id':pack['owner_id'],'used_seed':current,'next_seed':new})
    except ImportError:pass


def refine_seed(seed, policy='legacy', independent_seed='0', pass_index=0):
    base = int(seed_string(independent_seed if policy == 'independent' else seed))
    if policy == 'inherit': return base
    if policy in ('legacy', 'independent'): return (base + pass_index) & ((1 << 64)-1)
    if policy == 'offset': return (base + 1 + pass_index) & ((1 << 64)-1)
    raise ValueError('Unknown refinement seed policy.')


def refine_canvas(video, policy, megapixels, width, height):
    source = (int(video.shape[-1])*16, int(video.shape[-2])*16)
    if policy == 'follow':
        return plan_canvas({'mode':'auto','aspect':'auto','megapixels':megapixels}, source)
    if policy != 'manual': raise ValueError('Unknown refinement canvas policy.')
    return plan_canvas({'mode':'manual','width':width or source[0],'height':height or source[1]})
