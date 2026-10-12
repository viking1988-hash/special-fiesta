"""Strict fail-closed report for customer backup recovery verification.

JSON receipt fields are unauthenticated claims, NOT independent restore proof.
No network calls or credentials; JSON-only local evaluation.
"""
import json
import sys
from pathlib import Path

from backup.recoverability_status import backup_recoverability_status


def report(archive, receipt, now=None):
    status = backup_recoverability_status(archive, receipt, now)
    return {
        "status": "UNVERIFIED_SELF_REPORTED_RECEIPT" if status == "RECOVERY_VERIFIED" else status,
        "recovery_verified": False,
        "metadata_checks_passed": status == "RECOVERY_VERIFIED",
        "archive_present_is_not_proof": True,
        "independent_restore_evidence_required": True,
    }


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("USAGE: python3 -m backup.recovery_report ARCHIVE_JSON RECEIPT_JSON", file=sys.stderr)
        return 2
    try:
        paths = [Path(x) for x in argv]
        if any(not x.is_file() or x.stat().st_size > 16384 for x in paths):
            raise ValueError("INPUT_INVALID")
        archive, receipt = [json.loads(x.read_text(encoding="utf-8")) for x in paths]
        result = report(archive, receipt)
    except (OSError, ValueError, TypeError):
        print("RECOVERY_REPORT_INPUT_INVALID", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["recovery_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
