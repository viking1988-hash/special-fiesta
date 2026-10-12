import unittest
from datetime import datetime, timezone
from backup.recovery_report import report, main


class RecoveryReportTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)
        self.archive = {"name": "clients-20261012T110000Z.dump.age",
                        "size": 12345, "sha256": "a" * 64, "type": "file"}
        self.receipt = {
            "isolation": "isolated", "source": "encrypted-client-archive",
            "decryption": True, "restore": True, "row_digests_match": True,
            "foreign_keys_ok": True, "sequences_ok": True, "tenant_boundaries_ok": True,
            "archive_sha256": "a" * 64, "verified_at": "2026-10-12T11:30:00Z",
        }

    def test_self_reported_recovery_not_proof(self):
        result = report(self.archive, self.receipt, self.now)
        self.assertEqual(result["status"], "UNVERIFIED_SELF_REPORTED_RECEIPT")
        self.assertFalse(result["recovery_verified"])
        self.assertTrue(result["metadata_checks_passed"])
        self.assertTrue(result["independent_restore_evidence_required"])

    def test_archive_without_receipt_fails(self):
        result = report(self.archive, None, self.now)
        self.assertFalse(result["recovery_verified"])
        self.assertTrue(result["archive_present_is_not_proof"])

    def test_failed_restore_fails(self):
        result = report(self.archive, {**self.receipt, "restore": False}, self.now)
        self.assertFalse(result["recovery_verified"])

    def test_missing_inputs_fail_closed(self):
        self.assertEqual(main([]), 2)


if __name__ == "__main__":
    unittest.main()
