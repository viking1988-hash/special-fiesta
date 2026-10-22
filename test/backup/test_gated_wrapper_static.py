"""Static security invariants for the gated live export wrapper.

No live exporter is executed. This catches accidental removal of preflight,
approval gate, and synthetic-mode refusal in code review.
"""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "scripts/crm-clients-live-export-gated.sh"


class GatedWrapperStaticTests(unittest.TestCase):
    def test_bash_syntax(self):
        subprocess.run(["bash", "-n", str(WRAPPER)], check=True, timeout=5)

    def test_preflight_precedes_export(self):
        script = WRAPPER.read_text()
        preflight = script.index("python3 -m backup.live_export_preflight")
        exporter = script.index('bash "$here/crm-clients-export.sh" "$@"')
        self.assertLess(preflight, exporter)

    def test_scheduled_job_must_use_gated_wrapper(self):
        job = (ROOT / "scripts/crm-clients-backup-job.sh").read_text()
        self.assertIn('bash "$here/crm-clients-live-export-gated.sh" "$archive"', job)
        self.assertNotIn('bash "$here/crm-clients-export.sh" "$archive"', job)
        self.assertIn('export CLIENT_BACKUP_OUTPUT_DIR="$workdir"', job)
        self.assertIn('bash "$here/crm-clients-yandex-upload.sh" "$archive"', job)
        self.assertLess(job.index('bash "$here/crm-clients-live-export-gated.sh" "$archive"'),
                        job.index('bash "$here/crm-clients-yandex-upload.sh" "$archive"'))

    def test_no_silent_preflight_bypass(self):
        script = WRAPPER.read_text()
        self.assertIn("set -Eeuo pipefail", script)
        self.assertIn("CLIENT_BACKUP_LIVE_RUN_APPROVED", script)
        self.assertIn("SYNTHETIC_REHEARSAL_ONLY", script)
        self.assertNotIn("python3 -m backup.live_export_preflight || true", script)
        self.assertNotIn('bash scripts/crm-clients-export.sh "$@" || true', script)


if __name__ == "__main__":
    unittest.main()
