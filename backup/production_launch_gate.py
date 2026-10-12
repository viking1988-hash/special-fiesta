"""Fail-closed deployment authorization policy for optional client backups.

Evidence is manually reviewed by an operator; self-asserted environment flags
and JSON recovery receipts are not evidence. This module never authorizes
production solely from synthetic tests or metadata checks.
"""


REQUIRED_EVIDENCE = (
    "production_reader_acl_independently_verified",
    "offline_recovery_identity_independently_verified",
    "real_encrypted_archive_isolated_restore_verified",
    "archive_receipt_authenticity_verified",
    "privacy_and_retention_approved",
    "production_launch_explicitly_approved",
)


def evaluate(evidence):
    """Return a conservative status and missing independently reviewed gates."""
    if not isinstance(evidence, dict):
        evidence = {}
    missing = [key for key in REQUIRED_EVIDENCE if evidence.get(key) is not True]
    # Do not return a GO verdict: this code cannot authenticate attestations.
    return {
        "status": "NOT_AUTHORIZED",
        "missing_evidence": missing,
        "manual_independent_verification_required": True,
        "automated_launch_allowed": False,
    }
