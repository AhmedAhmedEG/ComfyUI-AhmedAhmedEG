"""Look grading must not compound along continuity chains."""
import unittest
from tests.mock_torch import setup_mock_torch_if_needed
torch = setup_mock_torch_if_needed()
from core.references import edit_images, undo_image_edits, look_is_active


class LookDoesNotCompound(unittest.TestCase):
    def frames(self):
        g = torch.Generator().manual_seed(1)
        return torch.rand((3, 8, 8, 3), generator=g) * 0.2 + 0.35   # mid-tones: the grades below do not clip

    def test_undo_recovers_the_generation(self):
        x = self.frames()
        for look in ({'exposure': 0.3, 'contrast': 1.2, 'saturation': 1.3},
                     {'exposure': -0.2, 'contrast': 0.8, 'saturation': 0.7, 'model': 'css'}):
            with self.subTest(look=look):
                self.assertTrue(torch.allclose(undo_image_edits(edit_images(x, look), look), x, atol=1e-5))

    def test_neutral_look_is_untouched(self):
        x = self.frames()
        self.assertFalse(look_is_active({'exposure': 0, 'contrast': 1, 'saturation': 1}))
        self.assertIs(undo_image_edits(x, {'exposure': 0, 'contrast': 1, 'saturation': 1}), x)
        self.assertIs(undo_image_edits(x, None), x)


if __name__ == '__main__':
    unittest.main()
