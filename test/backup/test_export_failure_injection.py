"""Synthetic failure injection for encrypted client export.

Never connects to PostgreSQL: fake pg_dump and age commands are injected via PATH.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/crm-clients-export.sh"


class ExportFailureTests(unittest.TestCase):
    def run_export(self, dump_exit=0, age_exit=0, malformed_header=False):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            commands = root / "bin"
            commands.mkdir()
            dump = commands / "pg_dump"
            dump.write_text("#!/bin/sh\nprintf 'synthetic only'\nexit " + str(dump_exit) + "\n")
            dump.chmod(0o700)
            age = commands / "age"
            age.write_text(
                "#!/bin/sh\n"
                "while [ \"$#\" -gt 0 ]; do\n"
                "  if [ \"$1\" = -o ]; then shift; out=$1; fi\n"
                "  shift\n"
                "done\n"
                + ("printf 'INVALID-ENCRYPTED-HEADER\\n' > \"$out\"\n" if malformed_header else "printf 'age-encryption.org/v1\\n' > \"$out\"\n")
                + "cat >> \"$out\"\n"
                + "exit " + str(age_exit) + "\n"
            )
            age.chmod(0o700)
            out = root / "clients-20261012T120000Z.dump.age"
            env = {
                "PATH": str(commands) + ":" + os.environ.get("PATH", ""),
                "CLIENT_BACKUP_ENABLED": "true",
                "CLIENT_BACKUP_SCHEMA_VERIFIED": "YES",
                "CLIENT_BACKUP_REQUIRE_ENCRYPTION": "true",
                "DATABASE_URL": "postgresql://synthetic@localhost/synthetic",
                "AGE_RECIPIENT": "age1" + "q" * 58,
            }
            result = subprocess.run(["bash", str(SCRIPT), str(out)], env=env,
                                    text=True, capture_output=True, timeout=5)
            return result, out.exists(), Path(str(out) + ".partial").exists()

    def test_cleanup_does_not_unlink_replaced_partial_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            commands = root / "bin"
            commands.mkdir()
            sentinel = root / "sentinel.txt"
            sentinel.write_text("must survive")
            out = root / "clients-20261012T120000Z.dump.age"
            partial = Path(str(out) + ".partial")
            dump = commands / "pg_dump"
            dump.write_text("#!/bin/sh\nprintf 'synthetic only'\n")
            dump.chmod(0o700)
            age = commands / "age"
            age.write_text(
                '#!/bin/sh\n'
                'while [ "$#" -gt 0 ]; do\n'
                '  if [ "$1" = -o ]; then shift; out=$1; fi\n'
                '  shift\n'
                'done\n'
                'ln -s "$SYNTHETIC_SENTINEL" "$out"\n'
                'exit 19\n'
            )
            age.chmod(0o700)
            env = {
                "PATH": str(commands) + ":" + os.environ.get("PATH", ""),
                "CLIENT_BACKUP_ENABLED": "true",
                "CLIENT_BACKUP_SCHEMA_VERIFIED": "YES",
                "CLIENT_BACKUP_REQUIRE_ENCRYPTION": "true",
                "DATABASE_URL": "postgresql://synthetic@localhost/synthetic",
                "AGE_RECIPIENT": "age1" + "q" * 58,
                "SYNTHETIC_SENTINEL": str(sentinel),
            }
            result = subprocess.run(["bash", str(SCRIPT), str(out)], env=env,
                                    text=True, capture_output=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(out.exists())
            self.assertTrue(partial.is_symlink())
            self.assertEqual(sentinel.read_text(), "must survive")

    def test_pg_dump_failure_never_publishes_archive(self):
        result, final, partial = self.run_export(dump_exit=17)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(final)
        self.assertFalse(partial)
        self.assertIn("CLIENT_BACKUP_EXPORT_FAILED", result.stderr)

    def test_age_failure_never_publishes_archive(self):
        result, final, partial = self.run_export(age_exit=18)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(final)
        self.assertFalse(partial)
        self.assertIn("CLIENT_BACKUP_EXPORT_FAILED", result.stderr)

    def test_malformed_header_never_publishes_archive(self):
        result, final, partial = self.run_export(malformed_header=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(final)
        self.assertFalse(partial)
        self.assertIn("CLIENT_BACKUP_INVALID_ENCRYPTED_HEADER", result.stderr)

    def test_synthetic_success_produces_only_final(self):
        result, final, partial = self.run_export()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(final)
        self.assertFalse(partial)


if __name__ == "__main__":
    unittest.main()
