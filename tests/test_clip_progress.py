"""Clip state remains queryable when an event is missed by the browser."""
import unittest
from unittest.mock import patch, Mock
from types import SimpleNamespace
import sys
from core import progress


class ClipProgress(unittest.TestCase):
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
