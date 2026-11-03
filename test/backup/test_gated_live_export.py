"""The gated live exporter must refuse unsafe invocation before any I/O."""
import os
from pathlib import Path
import subprocess
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/crm-clients-live-export-gated.sh"


class GatedLiveExportTests(unittest.TestCase):
    def run_script(self, env):
        clean = {"PATH": os.environ.get("PATH", "")}
        clean.update(env)
        return subprocess.run(["bash", str(SCRIPT), "/tmp/unused.age"],
                              env=clean, capture_output=True, text=True, timeout=5)

    def test_missing_configuration_from_unrelated_working_directory(self):
        clean = {"PATH": os.environ.get("PATH", ""),
                 "CLIENT_BACKUP_LIVE_RUN_APPROVED": "YES",
                 "CLIENT_BACKUP_ENABLED": "true"}
        result = subprocess.run(["bash", str(SCRIPT), "/tmp/unused.age"],
                                cwd="/tmp", env=clean, capture_output=True,
                                text=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CLIENT_EXPORT_PREFLIGHT_", result.stderr)
        self.assertNotIn("No module named backup", result.stderr)

    def test_default_refuses_without_approval(self):
        result = self.run_script({})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CLIENT_BACKUP_LIVE_APPROVAL_REQUIRED", result.stderr)

    def test_disabled_exporter_refuses_even_with_approval(self):
        result = self.run_script({"CLIENT_BACKUP_LIVE_RUN_APPROVED": "YES"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CLIENT_BACKUP_NOT_ENABLED", result.stderr)

    def test_synthetic_mode_refused_even_with_approval(self):
        result = self.run_script({"CLIENT_BACKUP_LIVE_RUN_APPROVED": "YES",
                                  "CLIENT_BACKUP_ENABLED": "true",
                                  "SYNTHETIC_REHEARSAL_ONLY": "YES"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CLIENT_BACKUP_SYNTHETIC_MODE_REFUSED", result.stderr)

    def test_missing_configuration_fails_before_export(self):
        result = self.run_script({"CLIENT_BACKUP_LIVE_RUN_APPROVED": "YES",
                                  "CLIENT_BACKUP_ENABLED": "true"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CLIENT_EXPORT_PREFLIGHT_", result.stderr)
        self.assertNotIn("CLIENT_BACKUP_ENCRYPTED_OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
