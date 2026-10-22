"""Demand-driven server telemetry. No Torch imports or GPU allocations."""
import csv
import io
import math
import os
import subprocess
import threading
import time

import psutil


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) and result >= 0 else None
    except (ValueError, TypeError):
        return None


def nvidia_stats():
    result = subprocess.run([
        'nvidia-smi', '--query-gpu=index,uuid,name,utilization.gpu,memory.used,memory.total',
        '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=1.5,
        check=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    devices = []
    for row in csv.reader(io.StringIO(result.stdout), skipinitialspace=True):
        if len(row) != 6:
            continue
        index, uid, name, utilization, used, total = (cell.strip() for cell in row)
        used, total = number(used), number(total)
        devices.append({'id': uid or index, 'index': index, 'name': name,
            'percent': min(100., number(utilization)) if number(utilization) is not None else None,
            'memory_used': used * 1048576 if used is not None else None,
            'memory_total': total * 1048576 if total is not None else None})
    return devices


class HardwareMonitor:
    def __init__(self, gpu_reader=nvidia_stats, cpu_reader=psutil.cpu_times,
                 clock=time.monotonic, wall_clock=time.time):
        self.gpu_reader, self.cpu_reader = gpu_reader, cpu_reader
        self.clock, self.wall_clock = clock, wall_clock
        self.lock = threading.Lock()
        self.cached = None
        self.sampled_at = -math.inf
        self.previous_cpu = None
        self.retry_gpu_at = -math.inf

    def snapshot(self):
        with self.lock:
            now = self.clock()
            if self.cached is not None and now - self.sampled_at < 2:
                return self.cached
            cpu = None
            try:
                times = self.cpu_reader()
                # Linux guest time is already included in user/nice.
                total = sum(times) - getattr(times, 'guest', 0) - getattr(times, 'guest_nice', 0)
                idle = times.idle + getattr(times, 'iowait', 0)
                if self.previous_cpu is not None:
                    old_total, old_idle, old_time = self.previous_cpu
                    delta = total - old_total
                    if delta > 0 and 0 < now - old_time <= 10:
                        cpu = max(0., min(100., 100 * (1 - (idle - old_idle) / delta)))
                self.previous_cpu = total, idle, now
            except (OSError, AttributeError):
                self.previous_cpu = None
            devices, gpu_error = [], None
            if now >= self.retry_gpu_at:
                try:
                    devices = self.gpu_reader()
                    if not devices:
                        raise ValueError('No devices')
                except (OSError, subprocess.SubprocessError, ValueError):
                    self.retry_gpu_at = now + 30
                    gpu_error = 'GPU telemetry unavailable'
            else:
                gpu_error = 'GPU telemetry unavailable'
            self.sampled_at = now
            self.cached = {'sampled_at': self.wall_clock(), 'cpu_percent': cpu,
                'cpu_scope': 'server_host', 'gpus': devices, 'gpu_error': gpu_error}
            return self.cached


hardware_monitor = HardwareMonitor()
