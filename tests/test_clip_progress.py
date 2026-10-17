"""Clip state remains queryable when an event is missed by the browser."""
import unittest
from unittest.mock import patch, Mock
from types import SimpleNamespace
import sys
from core import progress


class ClipProgress(unittest.TestCase):
    def test_live_preview_excludes_future_cached_clips_and_old_run_state(self):
        shots=[{'id':'one'},{'id':'two'},{'id':'three'}]
        graph={'5':{'class_type':'MiniMaxH3MasterNode','inputs':{'timeline_data':'{"project_id":"preview-scope"}'}}}
        queue=Mock();queue.get_current_queue.return_value=([(1,'current',graph,{})],[])
        server=SimpleNamespace(instance=SimpleNamespace(prompt_queue=queue,send_sync=Mock()))
        with patch.dict(sys.modules,{'server':SimpleNamespace(PromptServer=server)}):
            self.assertEqual(progress.preview_run_context('preview-scope',shots,queue)['clip_ids'],[])
            progress.shot_event('5','preview-scope','one','preparing')
            self.assertEqual(progress.preview_run_context('preview-scope',shots,queue)['clip_ids'],[])
            progress.shot_event('5','preview-scope','two','sampling')
            self.assertEqual(progress.preview_run_context('preview-scope',shots,queue)['clip_ids'],['one'])
            progress.shot_event('5','preview-scope','two','completed')
            self.assertEqual(progress.preview_run_context('preview-scope',shots,queue)['clip_ids'],['one','two'])
            progress.shot_event('5','preview-scope','three','first_pass_ready')
            self.assertEqual(progress.preview_run_context('preview-scope',shots,queue)['clip_ids'],['one','two'])
            self.assertEqual(progress.preview_run_context('preview-scope',shots,queue,'first_pass')['clip_ids'],['one','two','three'])
        queue.get_current_queue.return_value=([(2,'next-run',graph,{})],[])
        self.assertEqual(progress.preview_run_context('preview-scope',shots,queue)['clip_ids'],[])
        self.assertIsNone(progress.preview_run_context('unrelated',shots,queue))
        queue.get_current_queue.return_value=([],[])
        self.assertIsNone(progress.preview_run_context('preview-scope',shots,queue))

    def test_approved_future_take_is_reused_but_submitted_regeneration_wins(self):
        import json
        shots=[{'id':'one','validated':False},{'id':'two','validated':True}]
        def graph(clips):
            return {'5':{'class_type':'MiniMaxH3MasterNode','inputs':{'generation_mode':'All clips',
                'timeline_data':json.dumps({'project_id':'approved-preview','clips':clips})}}}
        queue=Mock();queue.get_current_queue.return_value=([(1,'run-approved',graph(shots),{})],[])
        self.assertEqual(progress.preview_run_context('approved-preview',shots,queue)['clip_ids'],['two'])
        server=SimpleNamespace(instance=SimpleNamespace(prompt_queue=queue,send_sync=Mock()))
        with patch.dict(sys.modules,{'server':SimpleNamespace(PromptServer=server)}):
            progress.shot_event('5','approved-preview','one','sampling')
            self.assertEqual(progress.preview_run_context('approved-preview',shots,queue)['clip_ids'],['two'])
            shots[0]['validated']=True
            self.assertEqual(progress.preview_run_context('approved-preview',shots,queue)['clip_ids'],['two'],
                'Checking after enqueue cannot expose the result being regenerated')
        queue.get_current_queue.return_value=([],[(2,'pending',graph([{'id':'one','validated':False},{'id':'two','validated':True}]),{})])
        self.assertEqual(progress.preview_run_context('approved-preview',shots,queue)['clip_ids'],['two'])

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
