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

    def test_archive_created_during_encryption_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            output = root / "clients-20261016T120000Z.dump.age"
            pg_dump = bin_dir / "pg_dump"
            pg_dump.write_text("#!/bin/sh\\nprintf 'synthetic-pg-dump'\\n".replace("\\n", "\n"))
            pg_dump.chmod(0o700)
            age = bin_dir / "age"
            age.write_text(
                "#!/bin/sh\n"
                "while [ \"$1\" != \"-o\" ]; do shift; done\n"
                "shift\n"
                "printf 'age-encryption.org/v1\\nFAKE' > \"$1\"\n"
                "printf 'ORIGINAL-ARCHIVE' > '" + str(output) + "'\n"
            )
            age.chmod(0o700)
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
            self.assertEqual(output.read_bytes(), b"ORIGINAL-ARCHIVE")
            self.assertFalse(Path(str(output) + ".partial").exists())

    def test_existing_archive_preserved(self):
        self.run_case("archive")

    def test_existing_partial_preserved(self):
        self.run_case("partial")


if __name__ == "__main__":
    unittest.main()
