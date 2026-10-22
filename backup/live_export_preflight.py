"""Fail-closed preflight for a proposed live encrypted client export.

No database connections, files, uploads, alerts, or side effects. This check
must pass before any live exporter is implemented or scheduled.
"""
import os
import re
import sys
from urllib.parse import urlsplit

REQUIRED = (
    "DATABASE_URL", "AGE_RECIPIENT_PRIMARY", "AGE_RECIPIENT_RECOVERY", "YANDEX_DISK_TOKEN",
    "CLIENT_BACKUP_YANDEX_PATH",
)
AGE_RECIPIENT = re.compile(r"age1[023456789acdefghjklmnpqrstuvwxyz]{58}$")


def check(env):
    errors = []
    for name in REQUIRED:
        if not env.get(name):
            errors.append("MISSING_" + name)
    if env.get("CLIENT_BACKUP_ENABLED") != "true":
        errors.append("EXPORT_NOT_ENABLED")
    if env.get("CLIENT_BACKUP_REQUIRE_ENCRYPTION") != "true":
        errors.append("ENCRYPTION_NOT_REQUIRED")
    if env.get("CLIENT_BACKUP_SCHEMA_VERIFIED") != "YES":
        errors.append("SCHEMA_NOT_VERIFIED")
    if env.get("CLIENT_BACKUP_READER_ACL_VERIFIED") != "YES":
        errors.append("READER_ACL_NOT_VERIFIED")
    if env.get("CLIENT_BACKUP_RECOVERY_KEY_OFFLINE") != "YES":
        errors.append("OFFLINE_KEY_NOT_VERIFIED")
    if env.get("CLIENT_BACKUP_YANDEX_PATH") != "app:/clients-backups":
        errors.append("DESTINATION_NOT_APPROVED")
    if env.get("SYNTHETIC_REHEARSAL_ONLY") == "YES":
        errors.append("SYNTHETIC_MODE_NOT_LIVE")
    primary = env.get("AGE_RECIPIENT_PRIMARY", "")
    recovery = env.get("AGE_RECIPIENT_RECOVERY", "")
    if not AGE_RECIPIENT.fullmatch(primary):
        errors.append("INVALID_AGE_RECIPIENT_PRIMARY")
    if not AGE_RECIPIENT.fullmatch(recovery):
        errors.append("INVALID_AGE_RECIPIENT_RECOVERY")
    if primary and recovery and primary == recovery:
        errors.append("AGE_RECIPIENTS_NOT_DISTINCT")
    try:
        url = urlsplit(env.get("DATABASE_URL", ""))
        if url.scheme not in ("postgres", "postgresql") or not url.hostname or not url.username:
            errors.append("INVALID_DATABASE_URL")
        if url.username in ("postgres", "root", "admin"):
            errors.append("PRIVILEGED_DATABASE_ROLE_REFUSED")
        if url.hostname in ("localhost", "127.0.0.1"):
            errors.append("LOCAL_DATABASE_REFUSED")
    except ValueError:
        errors.append("INVALID_DATABASE_URL")
    return errors


def main():
    errors = check(os.environ)
    if errors:
        for error in errors:
            print("CLIENT_EXPORT_PREFLIGHT_" + error, file=sys.stderr)
        return 1
    print("CLIENT_EXPORT_PREFLIGHT_CONFIG_OK")
    print("CLIENT_EXPORT_PREFLIGHT_REQUIRES_LIVE_ACL_AND_RECOVERY_EVIDENCE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
