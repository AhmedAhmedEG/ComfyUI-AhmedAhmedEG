"""Execution-scoped status text; no tensor inspection, GPU calls or polling."""
from contextvars import ContextVar
import time

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
            'label': label, 'step': step, 'steps': steps, 'active': active})


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
        result = self.encoder.encode_from_tokens_scheduled(*args, **kwargs)
        stage('Text conditioning ready · preparing visual/audio conditioning')
        return result
