"""Real filesystem and tensor checks for single-current-result retention."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch
from core.cache_manager import ProjectCacheManager
from core.preview import create_preview_plan


class ResultRetention(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manager = ProjectCacheManager('retention', self.temp.name)
        self.folder = Path(self.manager.project_dir)
        self.frames = torch.zeros((12, 32, 64, 3))
        self.audio = {'waveform': torch.zeros((1, 2, 16000)), 'sample_rate': 32000}
        self.latent = {'samples': torch.zeros((1, 24, 3, 4, 4))}

    def store(self, clip='one'):
        self.manager.store_clip_results(clip, 'fingerprint', self.latent, self.audio, self.frames)
        return self.manager._manifest['clips'][clip]['generation']

    def test_replacement_removes_old_files_but_preserves_other_clips(self):
        old = self.store()
        other = self.store('two')
        self.manager.store_source_media('one', self.frames, self.audio)
        new = self.store()
        self.assertNotEqual(old, new)
        self.assertFalse(list(self.folder.glob('*'+old+'*.pt')))
        self.assertEqual(len(list(self.folder.glob('*'+other+'*.pt'))), 3)
        self.assertEqual(len(list(self.folder.glob('*'+new+'*.pt'))), 3)
        self.assertNotIn('takes', self.manager._manifest)
        self.assertTrue(torch.equal(self.manager.load_clip_frames('one'), self.frames))

    def test_failed_replacement_preserves_current_and_removes_partial_files(self):
        old = self.store()
        original_files = set(self.folder.glob('*.pt'))
        save = self.manager._atomic_save
        count = 0
        def failing_save(data, path):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError('simulated full disk')
            return save(data, path)
        with patch.object(self.manager, '_atomic_save', side_effect=failing_save):
            with self.assertRaises(OSError):
                self.store()
        self.assertEqual(self.manager._manifest['clips']['one']['generation'], old)
        self.assertEqual(set(self.folder.glob('*.pt')), original_files)

    def test_legacy_history_cleanup_preserves_current_stages_and_foreign_files(self):
        old = self.store()
        old_row = dict(self.manager._manifest['clips']['one'], clip_id='one')
        old_files = {p: p.read_bytes() for p in self.folder.glob('*.pt')}
        current = self.store()
        for path, data in old_files.items():
            path.write_bytes(data)
        stage = self.manager.store_refine_pass('one', 1, self.frames, self.audio)
        draft = self.manager.store_first_pass('one', 'draft', self.latent, self.frames, self.audio)
        self.manager.update_clip_metadata('one', {'refine_passes': [stage], 'first_pass': draft})
        self.manager._manifest['takes'] = {old: old_row}
        self.manager.save_manifest()
        orphan = self.folder / 'clip_one_abandoned_latent.pt'
        orphan.write_bytes(b'orphan')
        foreign = self.folder / 'keep.pt'
        foreign.write_bytes(b'foreign')
        self.manager.prune_history(include_orphans=True)
        self.assertNotIn('takes', self.manager._manifest)
        self.assertFalse(orphan.exists())
        self.assertFalse(list(self.folder.glob('*'+old+'*.pt')))
        for token in (current, draft['generation']):
            self.assertEqual(len(list(self.folder.glob('*'+token+'*.pt'))), 3)
        self.assertTrue((self.folder / stage['frames']).is_file())
        self.assertTrue((self.folder / stage['audio']).is_file())
        self.assertEqual(foreign.read_bytes(), b'foreign')

    def test_replaced_preview_is_deleted_and_current_plan_changes(self):
        self.store()
        state = {'project_id': 'retention', 'clips': [{'id': 'one'}]}
        old = create_preview_plan(state, base_dir=self.temp.name)
        media = self.folder / 'previews' / (old['key']+'.mp4')
        media.write_bytes(b'cached preview')
        self.store()
        self.assertFalse(media.exists())
        self.assertFalse(media.with_suffix('.json').exists())
        current = create_preview_plan(state, base_dir=self.temp.name)
        self.assertNotEqual(current['key'], old['key'])
        self.assertEqual(current['clip_generations']['one'], self.manager._manifest['clips']['one']['generation'])

    def test_failed_draft_replacement_is_atomic(self):
        first = self.manager.store_first_pass('one', 'draft', self.latent, self.frames, self.audio)
        original = set(self.folder.glob('*.pt'))
        save = self.manager._atomic_save
        def failing_save(data, path):
            if path.endswith('_draft_frames.pt'):
                raise OSError('simulated failure')
            return save(data, path)
        with patch.object(self.manager, '_atomic_save', side_effect=failing_save):
            with self.assertRaises(OSError):
                self.manager.store_first_pass('one', 'draft2', self.latent, self.frames, self.audio)
        self.assertEqual(self.manager._manifest['first_pass']['one']['generation'], first['generation'])
        self.assertEqual(set(self.folder.glob('*.pt')), original)

    def test_completed_draft_kept_until_final_replacement(self):
        draft = self.manager.store_first_pass('one', 'draft', self.latent, self.frames, self.audio)
        self.store()
        self.manager.update_clip_metadata('one', {'first_pass': draft})
        self.manager.store_first_pass('one', 'new-draft', self.latent, self.frames, self.audio)
        self.assertEqual(len(list(self.folder.glob('*'+draft['generation']+'*.pt'))), 3)
        self.store()
        self.manager.update_clip_metadata('one', {'first_pass': None, 'refine_passes': []})
        self.assertFalse(list(self.folder.glob('*'+draft['generation']+'*.pt')))


if __name__ == '__main__':
    unittest.main()
