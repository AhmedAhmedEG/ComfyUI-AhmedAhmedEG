import ast
import hashlib
import unittest
from unittest.mock import patch

from tools import patch_h3_sla_capture as capture


SOURCE = '''from comfy.model_prefetch import pause_malloc_graph
def override(use_ck, q, k, v):
    if use_ck:
        out = _ck_sol_attn(q, k, v,
                           topk_ratio=.2)
    else:
        out = triton_attention(q, k, v)
    return out
'''


class CaptureGuardTests(unittest.TestCase):
    def candidate(self):
        with patch.object(capture, "EXPECTED_SHA", hashlib.sha256(SOURCE.encode()).hexdigest()):
            return capture.propose(SOURCE)

    def test_only_sparse_call_is_wrapped_and_arguments_are_preserved(self):
        candidate = self.candidate()
        before = ast.parse(SOURCE).body[1].body[0]
        after = ast.parse(candidate).body[1].body[0]
        self.assertIsInstance(after.body[0], ast.With)
        self.assertEqual(ast.dump(before.body[0]), ast.dump(after.body[0].body[0]))
        self.assertEqual(ast.dump(before.orelse[0]), ast.dump(after.orelse[0]))

    def test_uninspected_revision_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Uninspected SLA revision"):
            capture.propose(SOURCE)

    def test_repeated_application_is_noop(self):
        candidate = self.candidate()
        self.assertEqual(capture.propose(candidate), candidate)


if __name__ == "__main__":
    unittest.main()
