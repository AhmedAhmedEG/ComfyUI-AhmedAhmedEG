"""Cooperative prompt jobs: token stops locally and stream disconnect remotely."""
import threading,uuid,socket


class DraftCancelled(ValueError):pass


class DraftJob:
    def __init__(self):self.event=threading.Event();self._closer=None;self._lock=threading.RLock()
    def check(self):
        if self.event.is_set():raise DraftCancelled('Prompt draft cancelled.')
    def bind_response(self,response):
        def close():
            sock=getattr(getattr(getattr(response,'fp',None),'raw',None),'_sock',None)
            if sock:
                try:sock.shutdown(socket.SHUT_RDWR)
                except OSError:pass
            response.close()
        with self._lock:self._closer=close
        if self.event.is_set():close()
    def cancel(self):
        self.event.set()
        with self._lock:closer=self._closer
        if closer:closer()


_JOBS={};_LOCK=threading.RLock()


def start_job(job_id):
    job_id=str(uuid.UUID(job_id))
    with _LOCK:
        if job_id in _JOBS or len(_JOBS)>=4:raise ValueError('Prompt writer is busy; cancel or wait for its current job.')
        job=DraftJob();_JOBS[job_id]=job
    return job_id,job


def finish_job(job_id):
    with _LOCK:_JOBS.pop(job_id,None)


def cancel_job(job_id):
    with _LOCK:job=_JOBS.get(str(job_id))
    if job:job.cancel()
    return job is not None


def stopping_options(job,backend):
    if job is None:return {}
    from transformers import StoppingCriteria,StoppingCriteriaList
    class CancelCriteria(StoppingCriteria):
        def __call__(self,input_ids,scores,**kwargs):
            import torch
            return torch.full((input_ids.shape[0],),job.event.is_set(),dtype=torch.bool,device=input_ids.device)
    return {'stopping_criteria':StoppingCriteriaList([CancelCriteria()])}
