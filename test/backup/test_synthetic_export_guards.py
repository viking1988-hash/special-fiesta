"""Regression tests for synthetic export's fail-closed boundaries.

These tests use no secrets, database connections, or remote storage.
"""
import os
from pathlib import Path
import subprocess
import sys
import unittest

SCRIPT = Path(__file__).with_name("synthetic_export_rehearsal.py")


def execute(extra):
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", "/tmp"),
        **extra,
    }
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        env=env, capture_output=True, text=True, timeout=10,
    )


class SyntheticExportGuardsTests(unittest.TestCase):
    def test_disabled_without_explicit_synthetic_gate(self):
        result = execute({})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SYNTHETIC_ONLY_REQUIRED", result.stderr + result.stdout)

    def test_live_database_credentials_refused(self):
        result = execute({
            "SYNTHETIC_REHEARSAL_ONLY": "YES",
            "DATABASE_URL": "postgresql://test:dummy@localhost/test",
        })
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("LIVE_CREDENTIALS_REFUSED", result.stderr + result.stdout)

    def test_yandex_token_refused(self):
        result = execute({
            "SYNTHETIC_REHEARSAL_ONLY": "YES",
            "YANDEX_DISK_TOKEN": "dummy-token",
        })
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("LIVE_CREDENTIALS_REFUSED", result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
