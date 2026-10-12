import unittest
from datetime import datetime, timezone
from backup.recoverability_status import backup_recoverability_status


class RecoverabilityStatusTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)
        self.archive = {
            "name": "clients-20261012T110000Z.dump.age",
            "size": 12345, "sha256": "a" * 64, "type": "file",
        }
        self.receipt = {
            "isolation": "isolated", "source": "encrypted-client-archive",
            "decryption": True, "restore": True, "row_digests_match": True,
            "foreign_keys_ok": True, "sequences_ok": True, "tenant_boundaries_ok": True,
            "archive_sha256": "a" * 64, "verified_at": "2026-10-12T113000Z",
        }
        self.receipt["verified_at"] = "2026-10-12T11:30:00Z"

    def test_valid_matching_archive_and_restore(self):
        self.assertEqual(backup_recoverability_status(self.archive, self.receipt, self.now),
                         "UNVERIFIED_SELF_REPORTED_RECEIPT")

    def test_missing_receipt(self):
        self.assertEqual(backup_recoverability_status(self.archive, None, self.now),
                         "RESTORE_NOT_VERIFIED")

    def test_digest_mismatch(self):
        receipt = {**self.receipt, "archive_sha256": "b" * 64}
        self.assertEqual(backup_recoverability_status(self.archive, receipt, self.now),
                         "ARCHIVE_RECEIPT_MISMATCH")

    def test_stale_archive(self):
        archive = {**self.archive, "name": "clients-20261001T110000Z.dump.age"}
        self.assertEqual(backup_recoverability_status(archive, self.receipt, self.now),
                         "ARCHIVE_INVALID_OR_STALE")

    def test_failed_restore(self):
        receipt = {**self.receipt, "restore": False}
        self.assertEqual(backup_recoverability_status(self.archive, receipt, self.now),
                         "RESTORE_NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
