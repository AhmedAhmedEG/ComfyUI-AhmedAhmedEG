"""Keep all regression artifacts out of the user's project output folder."""
import tempfile
import unittest
from unittest.mock import patch


class CacheIsolatedTestCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.cache_root = temporary.name
        override = patch("core.cache_manager.get_cache_root_dir", return_value=self.cache_root)
        override.start()
        self.addCleanup(override.stop)
