"""Execution-scoped status text; no tensor inspection, GPU calls or polling."""
from contextvars import ContextVar
import time
import uuid

_current = ContextVar('mmx_stage_progress', default=None)


def _send(data):
    try:
        from server import PromptServer
        if PromptServer.instance is not None:
            PromptServer.instance.send_sync('minimax_director/stage', data)
    except Exception:
        pass  # A disconnected UI must never fail generation.


class StageProgress:
    def __init__(self, send=_send, clock=time.monotonic):
        self.send, self.clock = send, clock
        self.node = self.project = None
        self.clip = ''
        self.index = self.total = None
        self.last = None
        self.last_sent = -float('inf')
        self.run_id=uuid.uuid4().hex
        self.cache_stats={}
        self.cache_revision=0
        self.cache_updated=0
        self.cache_reasons={}

    def report(self, label, *, step=None, steps=None, active=True):
        if self.node is None:
            return
        identity = (label, self.clip, self.index, active, step, steps)
        now = self.clock()
        if identity == self.last or step is not None and now-self.last_sent < .25 and step != steps:
            return
        self.last, self.last_sent = identity, now
        self.send({'node': str(self.node), 'project_id': self.project,
            'clip_id': self.clip, 'index': self.index, 'total': self.total,
            'label': label, 'step': step, 'steps': steps, 'active': active,
            'cache_report':cache_report() if self is _current.get() else None})


def cache_event(name, outcome):
    reporter=_current.get()
    if reporter is None:return
    row=reporter.cache_stats.setdefault(reporter.clip,{}).setdefault(name,{'hit':0,'miss':0,'bypass':0})
    row[outcome]=row.get(outcome,0)+1
    reporter.cache_revision+=1;reporter.cache_updated=time.time()


def cache_report():
    reporter=_current.get()
    if reporter is None:return None
    return {'run_id':reporter.run_id,'revision':reporter.cache_revision,'updated_at':reporter.cache_updated,
        'stats':{name:dict(row) for name,row in reporter.cache_stats.get(reporter.clip,{}).items()},
        'run_preparation':{name:dict(row) for name,row in reporter.cache_stats.get('',{}).items()},
        'reasons':dict(reporter.cache_reasons.get(reporter.clip,{}))}


def cache_reason(name,reason):
    reporter=_current.get()
    if reporter is not None:reporter.cache_reasons.setdefault(reporter.clip,{})[name]=reason[:300]


def cache_clip(clip_id,index,total):
    reporter=_current.get()
    if reporter is not None:reporter.clip=clip_id;reporter.index=index;reporter.total=total


def stage(label, **kwargs):
    reporter = _current.get()
    if reporter is not None:
        reporter.report(label, **kwargs)


def bind(node, project):
    reporter = _current.get()
    if reporter is not None:
        reporter.node, reporter.project = node, project
        reporter.report('Reading project and settings')


def clip_stage(node, project, clip, phase, **data):
    reporter = _current.get()
    if reporter is None or str(reporter.node) != str(node):
        return
    if clip:
        reporter.clip = clip
    reporter.index = data.get('index', reporter.index)
    reporter.total = data.get('total', reporter.total)
    labels = {'preparing': 'Preparing clip and references',
        'sampling': 'Preparing H3 model for sampling', 'refining': 'Refining clip',
        'decoding': 'Decoding generated video and audio',
        'face_refining': 'Refining faces', 'completed': 'Clip saved',
        'first_pass_ready': 'First pass saved — waiting for approval'}
    if phase in labels:
        reporter.report(labels[phase])


class ProgressEncoder:
    """Delegate unchanged encoder calls while describing their boundaries."""
    def __init__(self, encoder): self.encoder = encoder
    def __getattr__(self, name): return getattr(self.encoder, name)
    def tokenize(self, *args, **kwargs):
        stage('Text encoder · preparing prompt and reference tokens')
        return self.encoder.tokenize(*args, **kwargs)
    def encode_from_tokens_scheduled(self, *args, **kwargs):
        stage('Text encoder · loading as needed and encoding prompt')
        from .run_resources import current_resources
        owner=current_resources()
        if owner is not None and owner.text_conditioning is not None:
            result=owner.text_conditioning.encode(self.encoder,args,kwargs)
        else:result = self.encoder.encode_from_tokens_scheduled(*args, **kwargs)
        stage('Text conditioning ready · preparing visual/audio conditioning')
        return result
