"""Validate live encrypted export output before invoking pg_dump.

Requires an existing private directory, a timestamped archive filename, and
an unused regular path. Reject symlinks and path traversal.
"""
import os
from pathlib import Path
import re
import stat
import sys

ARCHIVE_NAME = re.compile(r"clients-\d{8}T\d{6}Z\.dump\.age\Z")


def validate(directory, output):
    if not directory or not output:
        return False
    root, target = Path(directory), Path(output)
    if not root.is_absolute() or not target.is_absolute():
        return False
    if not ARCHIVE_NAME.fullmatch(target.name):
        return False
    try:
        if root.is_symlink() or target.parent.is_symlink() or target.is_symlink():
            return False
        if root.resolve(strict=True) != target.parent.resolve(strict=True):
            return False
        mode = root.stat().st_mode
        if not stat.S_ISDIR(mode) or mode & 0o077:
            return False
        if (target.exists() or target.with_name(target.name + ".partial").exists()
                or target.with_name(target.name + ".partial").is_symlink()):
            return False
    except (OSError, RuntimeError):
        return False
    return True


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or not validate(os.environ.get("CLIENT_BACKUP_OUTPUT_DIR"), argv[0]):
        print("CLIENT_BACKUP_OUTPUT_PATH_REFUSED", file=sys.stderr)
        return 1
    print("CLIENT_BACKUP_OUTPUT_PATH_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
