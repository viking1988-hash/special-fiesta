"""Regression tests: existing archive and partial files must never be overwritten.

Uses fake commands, never a real database or customer data.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/crm-clients-export.sh"


class ExistingArchiveTests(unittest.TestCase):
    def run_case(self, preexisting):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            marker = root / "command-was-run"
            for command in ("pg_dump", "age"):
                script = bin_dir / command
                script.write_text("#!/bin/sh\ntouch '" + str(marker) + "'\nexit 99\n")
                script.chmod(0o700)
            output = root / "clients-20261012T120000Z.dump.age"
            target = output if preexisting == "archive" else Path(str(output) + ".partial")
            target.write_bytes(b"DO-NOT-OVERWRITE")
            env = {
                "PATH": str(bin_dir) + ":" + os.environ.get("PATH", ""),
                "CLIENT_BACKUP_ENABLED": "true",
                "CLIENT_BACKUP_SCHEMA_VERIFIED": "YES",
                "CLIENT_BACKUP_REQUIRE_ENCRYPTION": "true",
                "DATABASE_URL": "postgresql://synthetic@localhost/synthetic",
                "AGE_RECIPIENT": "age1" + "q" * 58,
            }
            result = subprocess.run(["bash", str(SCRIPT), str(output)], env=env,
                                    capture_output=True, text=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(target.read_bytes(), b"DO-NOT-OVERWRITE")
            self.assertFalse(marker.exists())

    def test_existing_archive_preserved(self):
        self.run_case("archive")

    def test_existing_partial_preserved(self):
        self.run_case("partial")


if __name__ == "__main__":
    unittest.main()
