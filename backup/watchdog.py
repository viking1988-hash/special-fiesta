"""Read-only missing-run check; deploy separately only after release approval."""
import os
import sys
from yandex import Disk
import notify

if os.environ.get("CLIENT_BACKUP_MONITOR_ENABLED") != "true":
    print("CLIENT_BACKUP_MONITOR_DISABLED")
    sys.exit(0)
try:
    disk = Disk(os.environ.get("YANDEX_DISK_TOKEN"),
                os.environ.get("CLIENT_BACKUP_YANDEX_PATH", "app:/clients-backups"))
    disk.check_freshness()
    print("CLIENT_BACKUP_FRESHNESS_OK")
except Exception:
    print("CLIENT_BACKUP_FRESHNESS_FAILED", file=sys.stderr)
    try:
        notify.main()
    except Exception:
        print("CLIENT_BACKUP_ALERT_FAILED", file=sys.stderr)
    sys.exit(1)
