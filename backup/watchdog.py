"""Read-only missing-run check; deploy separately only after release approval."""
import os
import sys
from yandex import Disk
import notify

def main(disk_factory=Disk, now=None):
    if os.environ.get("CLIENT_BACKUP_MONITOR_ENABLED") != "true":
        print("CLIENT_BACKUP_MONITOR_DISABLED")
        return 0
    try:
        disk = disk_factory(os.environ.get("YANDEX_DISK_TOKEN"),
                            os.environ.get("CLIENT_BACKUP_YANDEX_PATH", "app:/clients-backups"))
        disk.check_freshness(now)
        print("CLIENT_BACKUP_FRESHNESS_OK")
        return 0
    except Exception:
        print("CLIENT_BACKUP_FRESHNESS_FAILED", file=sys.stderr)
        try:
            notify.main(reason="missing")
        except Exception:
            print("CLIENT_BACKUP_ALERT_FAILED", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
