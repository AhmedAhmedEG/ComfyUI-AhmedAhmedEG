import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.mock_torch import setup_mock_torch_if_needed
setup_mock_torch_if_needed()
from core.project_store import ServerProjectStore, ProjectConflict
from core.cache_manager import ProjectCacheManager


class ServerProjects(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.store = ServerProjectStore(self.root / "projects")
        self.timeline = {"version": 2, "clips": [{"id": "one", "seed": "18446744073709551615", "prompt": "Test"}],
                         "builder_state": {"reference_names": {"image_1": "Alice"}}}
        self.workflow = {"nodes": [{"id": 7, "type": "MiniMaxH3MasterNode"},
                                   {"id": 8, "type": "LoadImage", "widgets_values": ["alice.png"]}], "links": []}

    def save(self, project_id="project_a", name="My Film", revision=None):
        return self.store.save(project_id, name, self.timeline, self.workflow, 7, revision)

    def test_named_projects_reopen_in_fresh_session_with_same_cache_identity(self):
        cache = ProjectCacheManager("project_a", str(self.root / "cache"))
        latent = Path(cache.project_dir) / "clip_one_latent.pt"
        latent.write_bytes(b"large latent data stays here")
        self.save(name="فيلمي / My Film")
        fresh = ServerProjectStore(self.root / "projects")
        rows = fresh.list()
        self.assertEqual(rows[0]["name"], "فيلمي / My Film")
        project = fresh.load(rows[0]["project_id"])
        self.assertEqual(project["timeline"]["project_id"], cache.project_id)
        self.assertEqual(project["timeline"]["project_name"], "فيلمي / My Film")
        self.assertEqual(project["timeline"]["clips"][0]["seed"], "18446744073709551615")
        self.assertEqual(project["workflow"]["nodes"][1]["widgets_values"], ["alice.png"])
        embedded = json.loads(project["workflow"]["nodes"][0]["widgets_values_named"]["timeline_data"])
        self.assertEqual(embedded["project_name"], project["name"])
        self.assertEqual(embedded["server_revision"], project["revision"])
        self.assertEqual(latent.read_bytes(), b"large latent data stays here")
        self.assertNotIn("large latent", json.dumps(project))
        cache.clear_project_cache()
        self.assertEqual(fresh.load("project_a")["name"], "فيلمي / My Film", "Cache cleanup must not delete the saved project")

    def test_conflicting_sessions_cannot_silently_overwrite(self):
        first = self.save()
        second = self.save(name="Renamed", revision=first["revision"])
        with self.assertRaises(ProjectConflict):
            self.save(name="Stale", revision=first["revision"])
        self.assertEqual(self.store.load("project_a")["revision"], second["revision"])
        self.assertEqual(len(self.store.list()), 1)

    def test_delete_results_removes_takes_autosave_and_previews_only(self):
        cache = ProjectCacheManager("project_a", str(self.root / "cache"))
        directory = Path(cache.project_dir)
        (directory / "clip_one_latent.pt").write_bytes(b"latent")
        (directory / "autosave.json").write_text('{}')
        previews = directory / "previews"
        previews.mkdir()
        (previews / "preview.mp4").write_bytes(b"video")
        sibling = ProjectCacheManager("project_b", str(self.root / "cache"))
        untouched = Path(sibling.project_dir) / "clip_other_latent.pt"
        untouched.write_bytes(b"other project")
        self.save()
        cache.clear_project_cache()
        self.assertEqual(sorted(p.name for p in directory.iterdir()), ["manifest.json"])
        self.assertEqual(cache._manifest["clips"], {})
        self.assertEqual(untouched.read_bytes(), b"other project")
        self.assertEqual(self.store.load("project_a")["name"], "My Film")

    def test_multiple_projects_same_names_remain_distinct(self):
        self.save(); self.save("project_b")
        self.assertEqual({row["project_id"] for row in self.store.list()}, {"project_a", "project_b"})

    def test_invalid_save_does_not_replace_existing_document(self):
        first = self.save()
        for bad_name in ["", " " * 3, "a" * 129, "newline\nname"]:
            with self.assertRaises(ValueError):
                self.save(name=bad_name, revision=first["revision"])
        with self.assertRaises(ValueError):
            self.save("../outside")
        with self.assertRaises(ValueError):
            self.store.save("project_a", "Name", self.timeline, {"nodes": []}, 7, first["revision"])
        self.assertEqual(self.store.load("project_a")["revision"], first["revision"])

    def test_bad_file_does_not_break_listing_and_inputs_are_not_mutated(self):
        original = copy.deepcopy(self.timeline)
        self.save()
        self.assertEqual(self.timeline, original)
        (self.store.root / "bad.json").write_text("broken")
        self.assertEqual(len(self.store.list()), 1)
        with self.assertRaises(FileNotFoundError):
            self.store.load("missing")
        self.assertFalse((self.store.root / "missing.json").exists())

    def test_interrupted_write_preserves_previous_save(self):
        first = self.save()
        with patch("core.project_store.os.replace", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                self.save(name="Newer", revision=first["revision"])
        self.assertEqual(self.store.load("project_a")["name"], "My Film")
        self.assertEqual(list(self.store.root.glob("*.tmp")), [])

    def test_oversized_metadata_is_rejected_before_creating_document(self):
        with patch("core.project_store.MAX_DOCUMENT_BYTES", 10):
            with self.assertRaises(ValueError):
                self.save()
        self.assertFalse(self.store.root.exists())


if __name__ == "__main__":
    unittest.main()
