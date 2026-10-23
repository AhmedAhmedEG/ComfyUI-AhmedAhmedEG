import subprocess
import unittest
from collections import namedtuple
from unittest.mock import patch
from core.hardware_monitor import HardwareMonitor, nvidia_stats, attach_shared_memory


Times = namedtuple('Times', 'user idle iowait guest')


class HardwareMonitorTests(unittest.TestCase):
    def test_model_registry_shares_sample_cache_and_failure_is_isolated(self):
        now, reads = [0.], []
        def models():
            reads.append(1)
            if len(reads) > 1: raise RuntimeError('Registry changed')
            return {'available': True, 'models': [{'name': 'MiniMaxH3'}]}
        monitor = HardwareMonitor(lambda: [], lambda: Times(1, 1, 0, 0),
                                  lambda: now[0], model_reader=models)
        first = monitor.snapshot()
        self.assertEqual(first['retained_models']['models'][0]['name'], 'MiniMaxH3')
        self.assertGreater(first['process_memory']['rss_bytes'], 0)
        self.assertIs(first, monitor.snapshot())
        self.assertEqual(len(reads), 1)
        now[0] = 3
        self.assertFalse(monitor.snapshot()['retained_models']['available'])

    def test_cpu_deltas_shared_cache_and_idle_resume(self):
        now=[0.];ticks=iter([Times(100,100,0,10),Times(120,110,0,10),Times(160,120,0,10)])
        reads=[]
        def gpu():reads.append(1);return [{'id':'gpu'}]
        monitor=HardwareMonitor(gpu,lambda:next(ticks),lambda:now[0],lambda:1000+now[0])
        self.assertIsNone(monitor.snapshot()['cpu_percent'])
        now[0]=1;self.assertIs(monitor.snapshot(),monitor.cached);self.assertEqual(len(reads),1)
        now[0]=2;self.assertAlmostEqual(monitor.snapshot()['cpu_percent'],200/3)
        now[0]=30;self.assertIsNone(monitor.snapshot()['cpu_percent'])
        self.assertEqual(len(reads),3)

    def test_gpu_failure_backs_off_without_breaking_cpu(self):
        now=[0.];reads=[]
        def gpu():reads.append(1);raise subprocess.TimeoutExpired('nvidia-smi',1.5)
        monitor=HardwareMonitor(gpu,lambda:Times(now[0],now[0],0,0),lambda:now[0])
        self.assertEqual(monitor.snapshot()['gpus'],[])
        now[0]=2;sample=monitor.snapshot();self.assertEqual(sample['cpu_percent'],50)
        self.assertEqual(sample['gpu_error'],'GPU telemetry unavailable');self.assertEqual(len(reads),1)
        now[0]=31;monitor.snapshot();self.assertEqual(len(reads),2)

    def test_shared_memory_uses_resident_apertures_and_never_guesses_adapter(self):
        from core.wsl_gpu_memory import shared_segments
        self.assertEqual(shared_segments([(4, 0), (7, 1), (9, 1)]), 16)
        row={'name':'4090','shared_memory_used':16,'shared_memory_total':100}
        cards=[{'name':'4090'}];attach_shared_memory(cards,[row])
        self.assertEqual(cards[0]['shared_memory_used'],16)
        cards=[{'name':'4090'},{'name':'4090'}];attach_shared_memory(cards,[row])
        self.assertTrue(all('shared_memory_used' not in card for card in cards))

    def test_nvidia_query_handles_multiple_devices_and_unsupported_values(self):
        output='0, GPU-one, NVIDIA GeForce RTX 4090, 87, 1024, 24000\n1, GPU-two, "GPU, example", [N/A], [N/A], 8192\n'
        with patch('core.hardware_monitor.subprocess.run') as run:
            run.return_value.stdout=output;devices=nvidia_stats()
            self.assertEqual(run.call_args.kwargs['timeout'],1.5)
        self.assertEqual(devices[0]['percent'],87)
        self.assertEqual(devices[0]['memory_used'],1024*1048576)
        self.assertEqual(devices[1]['name'],'GPU, example')
        self.assertIsNone(devices[1]['percent']);self.assertIsNone(devices[1]['memory_used'])


if __name__=='__main__':unittest.main()
