"""Demand-driven server telemetry. No Torch imports or GPU allocations."""
import csv
import io
import math
import os
import subprocess
import sys
import threading
import time
import json
from pathlib import Path

import psutil
from .model_telemetry import retained_models


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


def shared_gpu_stats():
    if not sys.platform.startswith('linux') or not Path('/usr/lib/wsl/lib/libdxcore.so').is_file():
        return []
    result = subprocess.run([sys.executable, str(Path(__file__).with_name('wsl_gpu_memory.py'))],
        capture_output=True, text=True, timeout=1.5, check=True)
    rows = json.loads(result.stdout)
    return rows if isinstance(rows, list) else []


def attach_shared_memory(devices, rows):
    # DXCore names can be ambiguous with identical cards; never assign another
    # adapter's system-memory usage to the selected GPU.
    for device in devices:
        matches = [row for row in rows if row.get('name') == device.get('name')]
        if len(matches) == 1 and sum(d.get('name') == device.get('name') for d in devices) == 1:
            row = matches[0]
            used, total = number(row.get('shared_memory_used')), number(row.get('shared_memory_total'))
            if used is not None and total is not None and total > 0:
                device.update(shared_memory_used=used, shared_memory_total=total,
                    shared_memory_source=row.get('shared_memory_source'))


class HardwareMonitor:
    def __init__(self, gpu_reader=nvidia_stats, cpu_reader=psutil.cpu_times,
                 clock=time.monotonic, wall_clock=time.time, shared_reader=shared_gpu_stats,
                 model_reader=retained_models):
        self.gpu_reader, self.cpu_reader = gpu_reader, cpu_reader
        self.clock, self.wall_clock = clock, wall_clock
        self.lock = threading.Lock()
        self.cached = None
        self.sampled_at = -math.inf
        self.previous_cpu = None
        self.retry_gpu_at = -math.inf
        self.shared_reader = shared_reader
        self.retry_shared_at = -math.inf
        self.model_reader = model_reader

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
            if devices and now >= self.retry_shared_at:
                try:
                    shared = self.shared_reader()
                    attach_shared_memory(devices, shared)
                    if not shared:
                        self.retry_shared_at = now + 30
                except (OSError, subprocess.SubprocessError, ValueError, TypeError):
                    self.retry_shared_at = now + 30
            self.sampled_at = now
            self.cached = {'sampled_at': self.wall_clock(), 'cpu_percent': cpu,
                'cpu_scope': 'server_host', 'gpus': devices, 'gpu_error': gpu_error}
            try:
                self.cached['retained_models'] = self.model_reader()
            except Exception:
                self.cached['retained_models'] = {'available': False, 'models': []}
            try:
                memory = psutil.Process().memory_info()
                self.cached['process_memory'] = {'rss_bytes': memory.rss,
                    'swap_bytes': getattr(memory, 'swap', None)}
                # Linux exposes swap in the process status, not memory_info().
                if sys.platform.startswith('linux'):
                    for line in Path('/proc/self/status').read_text().splitlines():
                        if line.startswith('VmSwap:'):
                            self.cached['process_memory']['swap_bytes'] = int(line.split()[1]) * 1024
                            break
            except (OSError, ValueError, psutil.Error):
                pass
            return self.cached


hardware_monitor = HardwareMonitor()
