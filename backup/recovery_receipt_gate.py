"""Pure policy for reporting a customer backup as recovery-verified.

Never mistake an uploaded archive or a metadata-only freshness check for a
completed isolated restore. No I/O, credentials or database operations.
"""
from datetime import datetime, timedelta, timezone
import re

DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def recovery_verified(receipt, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(receipt, dict):
        return False
    if receipt.get("isolation") != "isolated" or receipt.get("source") != "encrypted-client-archive":
        return False
    if receipt.get("decryption") is not True or receipt.get("restore") is not True:
        return False
    if receipt.get("row_digests_match") is not True or receipt.get("foreign_keys_ok") is not True:
        return False
    if receipt.get("sequences_ok") is not True or receipt.get("tenant_boundaries_ok") is not True:
        return False
    sha = receipt.get("archive_sha256")
    if not isinstance(sha, str) or not DIGEST.fullmatch(sha):
        return False
    stamp = receipt.get("verified_at")
    if not isinstance(stamp, str):
        return False
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        return False
    return timedelta(0) <= now - parsed.astimezone(timezone.utc) <= timedelta(hours=36)
