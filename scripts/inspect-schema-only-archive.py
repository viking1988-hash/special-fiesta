#!/usr/bin/env python3
"""Offline inspection of a schema-only PostgreSQL custom-format archive.

Never connects to a database or S3, and never prints table rows.
Usage: python3 scripts/inspect-schema-only-archive.py /path/to/archive.dump
"""
import hashlib
from pathlib import Path
import re
import subprocess
import sys

DATA_ENTRY = re.compile(r"\b(TABLE DATA|BLOBS|BLOB|LARGE OBJECT|MATERIALIZED VIEW DATA)\b")


def inspect(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise ValueError("ARCHIVE_MUST_BE_REGULAR_FILE")
    size = path.stat().st_size
    if not 1024 <= size <= 500 * 1024 * 1024:
        raise ValueError("ARCHIVE_SIZE_REFUSED")
    with path.open("rb") as stream:
        if stream.read(5) != b"PGDMP":
            raise ValueError("ARCHIVE_FORMAT_REFUSED")
        stream.seek(0)
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    result = subprocess.run(["pg_restore", "--list", str(path)], capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ValueError("ARCHIVE_TOC_UNREADABLE")
    if any(DATA_ENTRY.search(line) for line in result.stdout.splitlines() if line and not line.startswith(";")):
        raise ValueError("ARCHIVE_CONTAINS_DATA_REFUSED")
    return f"SCHEMA_ONLY_TOC_PASS size={size} sha256={digest}"


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise ValueError("USAGE: inspect-schema-only-archive.py ARCHIVE")
        print(inspect(Path(sys.argv[1])))
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(str(exc) if isinstance(exc, ValueError) else "ARCHIVE_INSPECTION_FAILED", file=sys.stderr)
        raise SystemExit(1)
