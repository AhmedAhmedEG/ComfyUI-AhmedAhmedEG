"""Reference Pack holds H3's per-clip maximum: 9 images, 3 videos, 3 audios."""
import unittest
from tests.mock_torch import setup_mock_torch_if_needed
torch = setup_mock_torch_if_needed()
from nodes.node_ref_pack import MiniMaxH3RefPack


class RefPackLimits(unittest.TestCase):
    def test_nine_images_three_videos_three_audios(self):
        spec = MiniMaxH3RefPack.INPUT_TYPES()['optional']
        for name in [f'image_{i}' for i in range(1, 10)] + ['video_3', 'audio_3', 'video_3_audio', 'video_3_fps', 'image_9_name']:
            self.assertIn(name, spec)
        inputs = {f'image_{i}': torch.zeros((1, 8, 8, 3)) for i in range(1, 10)}
        inputs.update(video_3=torch.zeros((4, 64, 64, 3)), audio_3={'waveform': torch.zeros((1, 2, 480)), 'sample_rate': 48000})
        pack, = MiniMaxH3RefPack().pack(image_9_name='Ninth', **inputs)
        ids = [row['id'] for row in pack['refs']]
        self.assertEqual(ids, [f'image_{i}' for i in range(1, 10)] + ['video_3', 'audio_3'])
        self.assertEqual(next(r for r in pack['refs'] if r['id'] == 'image_9')['name'], 'Ninth')

    def test_existing_fields_keep_their_order(self):
        names = list(MiniMaxH3RefPack.INPUT_TYPES()['optional'])
        # Saved workflows map widget values by position too; new fields come after the originals.
        self.assertLess(names.index('refmod_library'), names.index('image_5_name'))
        self.assertLess(names.index('asset_edits'), names.index('image_5'))


if __name__ == '__main__':
    unittest.main()
