import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "backup"))
spec = importlib.util.spec_from_file_location("backup_notify", ROOT / "backup/notify.py")
n = importlib.util.module_from_spec(spec)
spec.loader.exec_module(n)


class AlertsTests(unittest.TestCase):
    def test_unconfigured_alert_makes_no_network_call(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(n.urllib.request, "build_opener") as opener:
            n.main()
            opener.assert_not_called()

    def test_failure_payload_no_secret_or_data(self):
        env = {"CLIENT_BACKUP_ALERTS_ENABLED": "true", "CLIENT_BACKUP_TELEGRAM_TOKEN": "123:FAKE",
               "CLIENT_BACKUP_TELEGRAM_CHAT_ID": "-123"}
        with patch.dict(os.environ, env, clear=True), patch.object(n.urllib.request, "build_opener") as opener:
            opener.return_value.open.return_value = io.BytesIO(b'{"ok":true}')
            n.main()
            req = opener.return_value.open.call_args[0][0]
            payload = json.loads(req.data)
            self.assertNotIn("FAKE", payload["text"])
            self.assertNotIn("DATABASE_URL", payload["text"])
            self.assertEqual(payload["chat_id"], "-123")

    def test_invalid_token_refused_before_network(self):
        with patch.dict(os.environ, {"CLIENT_BACKUP_ALERTS_ENABLED": "true",
                        "CLIENT_BACKUP_TELEGRAM_TOKEN": "../evil"}, clear=True):
            with self.assertRaises(ValueError):
                n.main()

    def test_job_failure_keeps_nonzero_status(self):
        env = dict(os.environ)
        env.update(CLIENT_BACKUP_ENABLED="true", CLIENT_BACKUP_SCHEMA_VERIFIED="NO",
                   CLIENT_BACKUP_ALERTS_ENABLED="false")
        result = subprocess.run(["bash", "scripts/crm-clients-backup-job.sh"], cwd=ROOT,
                                env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CLIENT_BACKUP_JOB_FAILED", result.stderr)


if __name__ == "__main__":
    unittest.main()
