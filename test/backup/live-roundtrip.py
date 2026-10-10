"""Authorized artificial-data-only Yandex acceptance test; no record diagnostics."""
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse

sys.path.insert(0, str(Path(__file__).parents[2] / "backup"))
from yandex import Disk, BackupError, digest


class ObservedDisk(Disk):
    def api(self, suffix="", method="GET", payload=None, **query):
        result = super().api(suffix, method, payload, **query)
        if suffix in ("/upload", "/download"):
            host = urllib.parse.urlsplit(result.get("href", "")).hostname or ""
            # Static categories only: never log a presigned URL or provider-supplied hostname.
            if host == "downloader.disk.yandex.ru":
                category = "YANDEX_DOWNLOADER_RU"
            elif host.endswith(".disk.yandex.net") or host.endswith(".storage.yandex.net"):
                category = "YANDEX_NET_STORAGE"
            else:
                category = "UNRECOGNIZED"
            print("SYNTHETIC_API_LINK stage=" + suffix[1:] + " host_category=" + category, flush=True)
        return result


def main():
    if (os.environ.get("SYNTHETIC_REHEARSAL_ONLY") != "YES"
            or os.environ.get("CLIENT_BACKUP_LIVE_YANDEX_TEST") != "true"
            or os.environ.get("CLIENT_BACKUP_YANDEX_PATH") != "app:/clients-backups-test"):
        raise BackupError("SYNTHETIC_TEST_GATE_REQUIRED")
    source, destination = map(Path, sys.argv[1:])
    destination.parent.mkdir(mode=0o700, exist_ok=True)
    disk = ObservedDisk(os.environ.get("YANDEX_DISK_TOKEN"), "app:/clients-backups-test")
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
