"""Actual read-only Disk metadata check and simulated 37-hour scheduler outage.

Does not upload, rename, patch, delete or change a real archive timestamp.
"""
import datetime as dt
import io
import os
from pathlib import Path
import re
import sys
from contextlib import redirect_stderr
sys.path.insert(0, str(Path(__file__).parents[2] / 'backup'))
from yandex import Disk
import watchdog

if os.environ.get('CLIENT_BACKUP_LIVE_WATCHDOG_TEST') != 'true' or os.environ.get('SYNTHETIC_REHEARSAL_ONLY') != 'YES':
    raise SystemExit('LIVE_WATCHDOG_TEST_DISABLED')
if os.environ.get('CLIENT_BACKUP_YANDEX_PATH') != 'app:/clients-backups-test':
    raise SystemExit('WATCHDOG_ARTIFICIAL_FOLDER_REQUIRED')
os.environ['CLIENT_BACKUP_MONITOR_ENABLED'] = 'true'
os.environ['CLIENT_BACKUP_ALERTS_ENABLED'] = 'false'
if watchdog.main() != 0:
    raise SystemExit('LIVE_WATCHDOG_FRESH_CHECK_FAILED')
os.environ['CLIENT_BACKUP_ALERTS_ENABLED'] = 'true'
os.environ['CLIENT_BACKUP_TEST_ALERT'] = 'YES'
log = io.StringIO()
with redirect_stderr(log):
    status = watchdog.main(now=dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=37))
accepted = re.search(r'CLIENT_BACKUP_TEST_ALERT_ACCEPTED message_id=([0-9]+)', log.getvalue())
if status != 1 or 'CLIENT_BACKUP_FRESHNESS_FAILED' not in log.getvalue() or not accepted:
    raise SystemExit('LIVE_WATCHDOG_STALE_ALERT_FAILED')
print('LIVE_WATCHDOG_OUTAGE_OK actual_disk_metadata=YES simulated_clock_offset_hours=37 writes=NONE exit=1 message_id=' + accepted.group(1), flush=True)
