"""Clip state remains queryable when an event is missed by the browser."""
import unittest
from unittest.mock import patch, Mock
from types import SimpleNamespace
import sys
from core import progress


class ClipProgress(unittest.TestCase):
    def test_queue_and_progress_never_hide_current_saved_results(self):
        import json
        shots=[{'id':cid,'validated':False} for cid in ('one','two','three')]
        ids=[shot['id'] for shot in shots]
        graph={'5':{'class_type':'MiniMaxH3MasterNode','inputs':{
            'timeline_data':json.dumps({'project_id':'retained-preview','clips':shots})}}}
        queue=Mock()
        server=SimpleNamespace(instance=SimpleNamespace(prompt_queue=queue,send_sync=Mock()))
        for mode in ('All clips','Next clip'):
            graph['5']['inputs']['generation_mode']=mode
            for running,pending in (([],[(1,'run',graph,{})]), ([(1,'run',graph,{})],[])):
                queue.get_current_queue.return_value=(running,pending)
                with patch.dict(sys.modules,{'server':SimpleNamespace(PromptServer=server)}):
                    for phase in ('preparing','sampling','completed','first_pass_ready'):
                        progress.shot_event('5','retained-preview','two',phase)
                        self.assertEqual(progress.preview_run_context('retained-preview',shots,queue)['clip_ids'],ids)
                self.assertIsNone(progress.preview_run_context('unrelated',shots,queue))
        graph['5']['inputs']['generation_mode']='Conditioning only'
        self.assertIsNone(progress.preview_run_context('retained-preview',shots,queue))
        queue.get_current_queue.return_value=([],[])
        self.assertIsNone(progress.preview_run_context('retained-preview',shots,queue))

    def test_reconnect_snapshot_is_scoped_to_live_prompt_and_subgraph(self):
        queue=Mock()
        queue.get_current_queue.return_value=([(1,'run-a',{}, {})],[])
        server=SimpleNamespace(instance=SimpleNamespace(prompt_queue=queue,send_sync=Mock()))
        with patch.dict(sys.modules,{'server':SimpleNamespace(PromptServer=server)}):
            progress.shot_event('outer:7','reconnect','second','sampling')
        state=progress.progress_snapshot('7','reconnect',queue)
        self.assertTrue(state['active'])
        self.assertEqual(state['state']['clip_id'],'second')
        queue.get_current_queue.return_value=([(2,'different-run',{}, {})],[])
        self.assertFalse(progress.progress_snapshot('7','reconnect',queue)['active'])
        queue.get_current_queue.return_value=([],[])
        self.assertFalse(progress.progress_snapshot('7','reconnect',queue)['active'])

    def test_two_clip_transition_snapshot_and_order(self):
        sender=Mock()
        with patch.dict(sys.modules,{"server":SimpleNamespace(PromptServer=SimpleNamespace(instance=SimpleNamespace(send_sync=sender)))}):
            progress.shot_event("audit","project","one","sampling")
            first=progress.current_clip_progress("audit","project")
            progress.shot_event("audit","project","one","completed")
            progress.shot_event("audit","project","two","sampling")
            second=progress.current_clip_progress("audit","project")
        self.assertEqual(second["clip_id"],"two")
        self.assertEqual(second["phase"],"sampling")
        self.assertGreater(second["sequence"],first["sequence"])
        self.assertEqual(sender.call_args.args[1],second)
        second["clip_id"]="changed"
        self.assertEqual(progress.current_clip_progress("audit","project")["clip_id"],"two")
        self.assertIsNone(progress.current_clip_progress("audit","other-project"))

    def test_snapshot_bound_and_no_retained_timeline(self):
        with patch.dict(sys.modules,{"server":SimpleNamespace(PromptServer=SimpleNamespace(instance=None))}):
            for i in range(65):progress.shot_event("bounded",str(i),"one","preparing")
            progress.shot_event("bounded","64","","timeline_ready",timeline={"clips":[]})
        self.assertLessEqual(len(progress._states),64)
        self.assertIsNone(progress.current_clip_progress("bounded","0"))
        self.assertIsNone(progress.current_clip_progress("bounded","64"))
