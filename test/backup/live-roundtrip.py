"""Authorized artificial-data-only Yandex acceptance test; no record diagnostics."""
import os
from pathlib import Path
import re
import sys
import urllib.error

sys.path.insert(0, str(Path(__file__).parents[2] / "backup"))
from yandex import Disk, BackupError, digest


def main():
    if (os.environ.get("SYNTHETIC_REHEARSAL_ONLY") != "YES"
            or os.environ.get("CLIENT_BACKUP_LIVE_YANDEX_TEST") != "true"
            or os.environ.get("CLIENT_BACKUP_YANDEX_PATH") != "app:/clients-backups-test"):
        raise BackupError("SYNTHETIC_TEST_GATE_REQUIRED")
    source, destination = map(Path, sys.argv[1:])
    destination.parent.mkdir(mode=0o700, exist_ok=True)
    disk = Disk(os.environ.get("YANDEX_DISK_TOKEN"), "app:/clients-backups-test")
    sha = disk.upload(source)
    disk.download(source.name, destination, sha)
    if digest(destination) != sha:
        raise BackupError("READBACK_DIGEST_MISMATCH")
    print("SYNTHETIC_LIVE_YANDEX_READBACK_OK bytes=" + str(source.stat().st_size) + " sha256=" + sha)


if __name__ == "__main__":
    try:
        main()
    except BackupError as error:
        code = str(error)
        if not re.fullmatch(r"[A-Z_]+", code):
            code = "VALIDATION_FAILED"
        print("SYNTHETIC_LIVE_YANDEX_FAILED code=" + code, file=sys.stderr)
        sys.exit(1)
    except urllib.error.HTTPError as error:
        print("SYNTHETIC_LIVE_YANDEX_FAILED http=" + str(error.code), file=sys.stderr)
        sys.exit(1)
    except Exception:
        print("SYNTHETIC_LIVE_YANDEX_FAILED", file=sys.stderr)
        sys.exit(1)
