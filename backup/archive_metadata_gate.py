"""Pure metadata validation for a planned encrypted client-backup archive.

No network access, credentials, filesystem writes or retention deletions.
"""
from datetime import datetime, timedelta, timezone
import re

NAME = re.compile(r"clients-(\d{8}T\d{6}Z)\.dump\.age\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MAX_BYTES = 2 * 1024**3


def validate_archive(metadata, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(metadata, dict):
        return False
    name = metadata.get("name")
    match = NAME.fullmatch(name) if isinstance(name, str) else None
    if not match:
        return False
    try:
        created = datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    size = metadata.get("size")
    sha = metadata.get("sha256")
    if type(size) is not int or not 0 < size <= MAX_BYTES:
        return False
    if not isinstance(sha, str) or not SHA256.fullmatch(sha):
        return False
    if metadata.get("type") != "file" or metadata.get("public_url") or metadata.get("public_key"):
        return False
    return timedelta(0) <= now - created <= timedelta(hours=36)


def evaluate_backup_set(items, now=None):
    if not isinstance(items, list):
        return False
    return any(validate_archive(item, now) for item in items)
