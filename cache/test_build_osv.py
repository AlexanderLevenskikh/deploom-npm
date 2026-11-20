import gzip
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from zipfile import ZipFile

from build_osv import build_index


class IndexTest(unittest.TestCase):
    def test_index_preserves_versions_and_excludes_withdrawn_advisories(self):
        archive = io.BytesIO()
        affected = [{"package": {"name": "fixture", "ecosystem": "npm"}, "versions": ["1.0.0"]}]
        with ZipFile(archive, "w") as z:
            z.writestr("open.json", json.dumps({"id": "OSV-1", "affected": affected}))
            z.writestr("withdrawn.json", json.dumps({"id": "OSV-2", "withdrawn": "2024-01-01", "affected": affected}))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            target = path / "release"
            manifest = build_index(archive, 123456, target)
            self.assertEqual(manifest, json.loads((target / "manifest.json").read_bytes()))
            data = (target / manifest["asset"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), manifest["sha256"])
            self.assertEqual(len(data), manifest["size"])
            db = path / "test.sqlite"
            db.write_bytes(gzip.decompress(data))
            conn = sqlite3.connect(db)
            try:
                self.assertEqual(conn.execute("SELECT name,id,versions FROM advisory").fetchall(), [("fixture", "OSV-1", '["1.0.0"]')])
            finally:
                conn.close()
            self.assertEqual(build_index(archive, 123456, path / "repeat"), manifest)
