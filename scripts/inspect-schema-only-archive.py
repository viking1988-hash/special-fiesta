#!/usr/bin/env python3
"""Offline inspection of a schema-only PostgreSQL custom-format archive.

Never connects to a database or S3, and never prints table rows.
Usage: python3 scripts/inspect-schema-only-archive.py /path/to/archive.dump
"""
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile

DATA_ENTRY = re.compile(r"\b(TABLE DATA|BLOBS|BLOB|LARGE OBJECT|MATERIALIZED VIEW DATA)\b")


def inspect(path: Path) -> str:
    # Pin the source inode and inspect a private immutable snapshot, not the caller's
    # potentially replaceable pathname. O_NONBLOCK also fails safely for FIFOs.
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_NONBLOCK"):
        raise ValueError("ARCHIVE_SAFE_OPEN_UNAVAILABLE")
    flags |= os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise ValueError("ARCHIVE_MUST_BE_REGULAR_FILE") from exc
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("ARCHIVE_MUST_BE_REGULAR_FILE")
        size = metadata.st_size
        if not 1024 <= size <= 500 * 1024 * 1024:
            raise ValueError("ARCHIVE_SIZE_REFUSED")
        with tempfile.TemporaryDirectory(prefix="schema-inspect-") as private_dir:
            snapshot = Path(private_dir) / "archive.dump"
            digest = hashlib.sha256()
            with os.fdopen(fd, "rb", closefd=False) as source, snapshot.open("xb") as output:
                header = source.read(5)
                if header != b"PGDMP":
                    raise ValueError("ARCHIVE_FORMAT_REFUSED")
                output.write(header)
                digest.update(header)
                copied = 5
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    copied += len(chunk)
                    if copied > size:
                        raise ValueError("ARCHIVE_CHANGED_DURING_READ")
                    digest.update(chunk)
                    output.write(chunk)
            if copied != size or os.fstat(fd).st_size != size:
                raise ValueError("ARCHIVE_CHANGED_DURING_READ")
            result = subprocess.run(["pg_restore", "--list", str(snapshot)], capture_output=True, text=True, timeout=30)
    finally:
        os.close(fd)
    if result.returncode:
        raise ValueError("ARCHIVE_TOC_UNREADABLE")
    if any(DATA_ENTRY.search(line) for line in result.stdout.splitlines() if line and not line.startswith(";")):
        raise ValueError("ARCHIVE_CONTAINS_DATA_REFUSED")
    for table in ("customers", "vehicles"):
        pattern = re.compile(r"^\d+; \d+ \d+ TABLE public " + table + r" ")
        if not any(pattern.search(line) for line in result.stdout.splitlines()):
            raise ValueError("ARCHIVE_REQUIRED_CLIENT_TABLE_MISSING")
    return f"SCHEMA_ONLY_TOC_PASS size={size} sha256={digest.hexdigest()}"


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise ValueError("USAGE: inspect-schema-only-archive.py ARCHIVE")
        print(inspect(Path(sys.argv[1])))
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(str(exc) if isinstance(exc, ValueError) else "ARCHIVE_INSPECTION_FAILED", file=sys.stderr)
        raise SystemExit(1)
