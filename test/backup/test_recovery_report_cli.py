"""Black-box CLI tests: malformed input must fail without exposing file data."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from backup.recovery_report import main


class RecoveryReportCliTests(unittest.TestCase):
    def run_cli(self, archive_text, receipt_text):
        with tempfile.TemporaryDirectory() as directory:
            a, r = Path(directory) / "archive.json", Path(directory) / "receipt.json"
            a.write_text(archive_text, encoding="utf-8")
            r.write_text(receipt_text, encoding="utf-8")
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = main([str(a), str(r)])
            return code, stdout.getvalue(), stderr.getvalue()

    def test_malformed_json_rejected_without_echoing_data(self):
        secret = "PRIVATE_TEST_MARKER_NEVER_ECHO"
        code, out, err = self.run_cli('{"data": "' + secret, "{}")
        self.assertEqual(code, 2)
        self.assertNotIn(secret, out + err)
        self.assertIn("RECOVERY_REPORT_INPUT_INVALID", err)

    def test_missing_receipt_not_reported_as_success(self):
        archive = {"name": "clients-20261012T110000Z.dump.age",
                   "size": 1200, "sha256": "a" * 64, "type": "file"}
        code, out, err = self.run_cli(json.dumps(archive), "null")
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(out)["recovery_verified"])

    def test_oversized_input_rejected(self):
        code, out, err = self.run_cli(" " * 16385, "{}")
        self.assertEqual(code, 2)
        self.assertIn("RECOVERY_REPORT_INPUT_INVALID", err)


if __name__ == "__main__":
    unittest.main()
