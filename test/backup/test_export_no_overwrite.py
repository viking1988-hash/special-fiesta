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
                "AGE_RECIPIENT_PRIMARY": "age1" + "q" * 58,
            "AGE_RECIPIENT_RECOVERY": "age1" + "p" * 58,
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
                "AGE_RECIPIENT_PRIMARY": "age1" + "q" * 58,
            "AGE_RECIPIENT_RECOVERY": "age1" + "p" * 58,
            }
            result = subprocess.run(["bash", str(SCRIPT), str(output)], env=env,
                                    capture_output=True, text=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_bytes(), b"ORIGINAL-ARCHIVE")
            self.assertFalse(Path(str(output) + ".partial").exists())

    def test_dangling_symlink_created_during_encryption_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            output = root / "clients-20261016T120001Z.dump.age"
            missing_target = root / "not-created"
            dump = bin_dir / "pg_dump"
            dump.write_text("#!/bin/sh\\nprintf 'synthetic'\\n".replace("\\n", "\n"))
            dump.chmod(0o700)
            age = bin_dir / "age"
            age.write_text(
                "#!/bin/sh\n"
                "while [ \"$1\" != \"-o\" ]; do shift; done\n"
                "shift\n"
                "printf 'age-encryption.org/v1\\nFAKE' > \"$1\"\n"
                "ln -s '" + str(missing_target) + "' '" + str(output) + "'\n"
            )
            age.chmod(0o700)
            env = {
                "PATH": str(bin_dir) + ":" + os.environ.get("PATH", ""),
                "CLIENT_BACKUP_ENABLED": "true",
                "CLIENT_BACKUP_SCHEMA_VERIFIED": "YES",
                "CLIENT_BACKUP_REQUIRE_ENCRYPTION": "true",
                "DATABASE_URL": "postgresql://synthetic@localhost/synthetic",
                "AGE_RECIPIENT_PRIMARY": "age1" + "q" * 58,
            "AGE_RECIPIENT_RECOVERY": "age1" + "p" * 58,
            }
            result = subprocess.run(["bash", str(SCRIPT), str(output)], env=env,
                                    capture_output=True, text=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(output.is_symlink())
            self.assertEqual(output.readlink(), missing_target)
            self.assertFalse(missing_target.exists())
            self.assertFalse(Path(str(output) + ".partial").exists())

    def test_swapped_partial_after_hardlink_refuses_success(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            output = root / "clients-20261016T120002Z.dump.age"
            dump = bin_dir / "pg_dump"
            dump.write_text("#!/bin/sh\\nprintf 'synthetic'\\n".replace("\\n", "\n"))
            dump.chmod(0o700)
            age = bin_dir / "age"
            age.write_text(
                "#!/bin/sh\n"
                "while [ \"$1\" != \"-o\" ]; do shift; done\n"
                "shift\n"
                "printf 'age-encryption.org/v1\\nFAKE' > \"$1\"\n"
            )
            age.chmod(0o700)
            link = bin_dir / "ln"
            link.write_text(
                "#!/bin/sh\n"
                "/bin/ln \"$@\" || exit $?\n"
                "rm -- \"$2\"\n"
                "printf 'age-encryption.org/v1\\nSWAPPED' > \"$2\"\n"
            )
            link.chmod(0o700)
            env = {
                "PATH": str(bin_dir) + ":" + os.environ.get("PATH", ""),
                "CLIENT_BACKUP_ENABLED": "true",
                "CLIENT_BACKUP_SCHEMA_VERIFIED": "YES",
                "CLIENT_BACKUP_REQUIRE_ENCRYPTION": "true",
                "DATABASE_URL": "postgresql://synthetic@localhost/synthetic",
                "AGE_RECIPIENT_PRIMARY": "age1" + "q" * 58,
                "AGE_RECIPIENT_RECOVERY": "age1" + "p" * 58,
            }
            result = subprocess.run(["bash", str(SCRIPT), str(output)], env=env,
                                    capture_output=True, text=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("CLIENT_BACKUP_PUBLISHED_INODE_MISMATCH", result.stderr)
            self.assertNotIn("CLIENT_BACKUP_ENCRYPTED_OK", result.stdout)

    def test_swapped_partial_before_hardlink_refuses_success(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            output = root / "clients-20261016T120003Z.dump.age"
            dump = bin_dir / "pg_dump"
            dump.write_text("#!/bin/sh\\nprintf 'synthetic'\\n".replace("\\n", "\n"))
            dump.chmod(0o700)
            age = bin_dir / "age"
            age.write_text(
                "#!/bin/sh\n"
                "while [ \"$1\" != \"-o\" ]; do shift; done\n"
                "shift\n"
                "printf 'age-encryption.org/v1\\nORIGINAL' > \"$1\"\n"
            )
            age.chmod(0o700)
            link = bin_dir / "ln"
            link.write_text(
                "#!/bin/sh\n"
                "printf 'age-encryption.org/v1\\nSWAPPED' > \"$2\"\n"
                "/bin/ln \"$@\"\n"
            )
            link.chmod(0o700)
            env = {
                "PATH": str(bin_dir) + ":" + os.environ.get("PATH", ""),
                "CLIENT_BACKUP_ENABLED": "true",
                "CLIENT_BACKUP_SCHEMA_VERIFIED": "YES",
                "CLIENT_BACKUP_REQUIRE_ENCRYPTION": "true",
                "DATABASE_URL": "postgresql://synthetic@localhost/synthetic",
                "AGE_RECIPIENT_PRIMARY": "age1" + "q" * 58,
                "AGE_RECIPIENT_RECOVERY": "age1" + "p" * 58,
            }
            result = subprocess.run(["bash", str(SCRIPT), str(output)], env=env,
                                    capture_output=True, text=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("CLIENT_BACKUP_PUBLISHED_DIGEST_MISMATCH", result.stderr)
            self.assertNotIn("CLIENT_BACKUP_ENCRYPTED_OK", result.stdout)

    def test_existing_archive_preserved(self):
        self.run_case("archive")

    def test_existing_partial_preserved(self):
        self.run_case("partial")


if __name__ == "__main__":
    unittest.main()
