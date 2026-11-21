"""Exercise the actual Git object guard and the Node/Python signature boundary."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class IntakeTests(unittest.TestCase):
    def setUp(self):
        import records_intake
        self.intake = records_intake
        self.original = Path.cwd()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        os.chdir(self.temp.name)
        self.addCleanup(os.chdir, self.original)
        self.path = Path("docs/v1/history.json")
        self.path.parent.mkdir(parents=True)
        self.path.write_text("[]")
        subprocess.run(["git", "init", "-q"], check=True)
        fixture = Path("fixtures/react")
        fixture.mkdir(parents=True)
        import hashlib
        row = {"package": "react", "from": "18.2.0", "to": "18.3.1", "check": "test", "outcome": "passed"}
        (fixture / "evidence.json").write_text(json.dumps({"fixtureSha256": hashlib.sha256(
            b"react 18.2.0 18.3.1").hexdigest(), "claims": [row]}))
        self.base = self.commit()

    def commit(self):
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                        "commit", "-qm", "fixture"], check=True)
        return self.intake.git("rev-parse", "HEAD").decode().strip()

    def test_only_small_append_only_regular_data(self):
        row = {"schema": 1, "package": "react", "from": "18.2.0", "to": "18.3.1",
               "source": "https://github.com/levencode-labs/deploom-npm/blob/" + "a"*40 + "/fixtures/react/check.cjs",
               "check": "test", "outcome": "passed"}
        self.path.write_text(json.dumps([row]))
        head = self.commit()
        with patch.object(self.intake, "npm_version"), patch.object(self.intake, "evidence", return_value="react 18.2.0 18.3.1"):
            self.assertEqual(self.intake.inspect_pr(self.base, head)[0]["record"], row)
        self.path.write_text("[]")
        with self.assertRaisesRegex(ValueError, "removals"):
            self.intake.inspect_pr(head, self.commit())
        self.path.write_text(json.dumps([dict(row, to=f"18.3.{i}") for i in range(12)]))
        with self.assertRaisesRegex(ValueError, "many"):
            self.intake.inspect_pr(self.base, self.commit())
        Path("code.cjs").write_text("/* manual review */")
        with self.assertRaisesRegex(ValueError, "data-only"):
            self.intake.inspect_pr(self.base, self.commit())

    def test_evidence_must_come_from_main(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.intake.evidence(self.base, "https://github.com/levencode-labs/deploom-npm/blob/" +
                                 "0"*40 + "/fixtures/test/check.cjs")
