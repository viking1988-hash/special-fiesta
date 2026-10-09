"""Authorized one-shot notification through the actual backup failure trap."""
import os
import re
import subprocess

if os.environ.get("CLIENT_BACKUP_LIVE_ALERT_TEST") != "true" or os.environ.get("SYNTHETIC_REHEARSAL_ONLY") != "YES":
    raise SystemExit("LIVE_ALERT_TEST_DISABLED")
env = dict(os.environ)
env.update(CLIENT_BACKUP_ENABLED="true", CLIENT_BACKUP_SCHEMA_VERIFIED="NO",
           CLIENT_BACKUP_ALERTS_ENABLED="true", CLIENT_BACKUP_TEST_ALERT="YES")
env.pop("DATABASE_URL", None)
result = subprocess.run(["bash", "scripts/crm-clients-backup-job.sh"], env=env,
                        capture_output=True, text=True, timeout=30)
accepted = re.search(r"CLIENT_BACKUP_TEST_ALERT_ACCEPTED message_id=([0-9]+)", result.stderr)
if result.returncode != 1 or "CLIENT_BACKUP_JOB_FAILED" not in result.stderr or not accepted:
    raise SystemExit("LIVE_ALERT_FAILURE_TRAP_TEST_FAILED")
print("LIVE_ALERT_FAILURE_TRAP_OK exit=1 message_id=" + accepted.group(1), flush=True)
