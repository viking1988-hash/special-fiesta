"""Pure policy: distinguish uploaded archives from recovery-proven archives.

The receipt must attest to the *same* SHA256 as the archived object. This
module does not connect to databases, Yandex Disk, or Telegram.
"""
from backup.archive_metadata_gate import validate_archive
from backup.recovery_receipt_gate import recovery_verified


def backup_recoverability_status(archive, receipt, now=None):
    if not validate_archive(archive, now):
        return "ARCHIVE_INVALID_OR_STALE"
    if not recovery_verified(receipt, now):
        return "RESTORE_NOT_VERIFIED"
    if archive["sha256"] != receipt["archive_sha256"]:
        return "ARCHIVE_RECEIPT_MISMATCH"
    # A matching, self-reported receipt is not independent restore evidence.
    return "UNVERIFIED_SELF_REPORTED_RECEIPT"
