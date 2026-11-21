import json
from pathlib import Path
import tempfile
import unittest

from assemble import ROOT, windows_cli_version


class WindowsArchiveVersionTests(unittest.TestCase):
    def test_official_manifest_is_preserved_and_development_wheel_has_own_install_path(self):
        original = (ROOT / "package.json").read_bytes()
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp)
            path = package / "package.json"
            path.write_bytes(original)
            self.assertEqual(windows_cli_version(package, "0.2.21"), json.loads(original)["version"])
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(windows_cli_version(package, "0.2.22.dev2"), "0.2.22-preview.2")
            expected = {**json.loads(original), "version": "0.2.22-preview.2", "os": ["win32"], "cpu": ["x64"]}
            self.assertEqual(json.loads(path.read_bytes()), expected)
