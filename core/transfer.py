"""Small transfer progress events shared by project import/export routes."""
import time
import uuid


def progress_callback(server, job_id):
    if not job_id:
        return lambda *args: None
    job_id = str(uuid.UUID(str(job_id)))
    last = [0.]
    def report(phase, done, total):
        now = time.monotonic()
        if done < total and now-last[0] < .1:
            return
        last[0] = now
        server.send_sync('minimax_transfer', {'job_id': job_id, 'phase': phase,
            'done': int(done), 'total': int(total)})
    return report


def copy_progress(source, target, report, phase, offset, total):
    count = 0
    while chunk := source.read(1024*1024):
        target.write(chunk)
        count += len(chunk)
        report(phase, offset+count, total)
    return count
