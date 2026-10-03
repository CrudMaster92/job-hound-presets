import shutil
import subprocess
import unittest
from pathlib import Path


class BrowserSelectionTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is required for browser contract tests')
    def test_large_collection_and_exact_bounded_handoffs(self):
        subprocess.run(['node', str(Path(__file__).with_name('browser_selection.cjs'))], check=True)
