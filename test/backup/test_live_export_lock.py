import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "scripts/crm-clients-live-export-gated.sh"


class LiveExportLockTests(unittest.TestCase):
    def test_lock_is_exclusive_and_private(self):
        with tempfile.TemporaryDirectory() as d:
            lock = Path(d) / "archive.live-lock"
            first = subprocess.run(["mkdir", "-m", "700", str(lock)], check=False)
            second = subprocess.run(["mkdir", "-m", "700", str(lock)], check=False,
                                    capture_output=True)
            self.assertEqual(first.returncode, 0)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(lock.stat().st_mode & 0o777, 0o700)

    def test_wrapper_refuses_preexisting_lock_without_export(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "clients-20261012T120000Z.dump.age"
            lock = Path(str(out) + ".live-lock")
            lock.mkdir(mode=0o700)
            # Source inspection: actual wrapper is never run with live credentials.
            source = WRAPPER.read_text()
            self.assertIn('if ! mkdir -m 700 -- "$lock"', source)
            self.assertIn("CLIENT_BACKUP_CONCURRENT_EXPORT_REFUSED", source)
            self.assertLess(source.index('if ! mkdir -m 700 -- "$lock"'),
                            source.index('bash "$here/crm-clients-export.sh" "$@"'))

    def test_shell_syntax(self):
        subprocess.run(["bash", "-n", str(WRAPPER)], check=True, timeout=5)


if __name__ == "__main__":
    unittest.main()
