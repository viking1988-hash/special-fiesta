import unittest
from datetime import datetime, timezone
from backup.recovery_receipt_gate import recovery_verified


class RecoveryReceiptGateTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)
        self.receipt = {
            "isolation": "isolated",
            "source": "encrypted-client-archive",
            "decryption": True,
            "restore": True,
            "row_digests_match": True,
            "foreign_keys_ok": True,
            "sequences_ok": True,
            "tenant_boundaries_ok": True,
            "archive_sha256": "a" * 64,
            "verified_at": "2026-10-12T11:00:00Z",
        }

    def test_complete_receipt(self):
        self.assertTrue(recovery_verified(self.receipt, self.now))

    def test_missing_or_false_evidence_refused(self):
        for key in ("decryption", "restore", "row_digests_match", "foreign_keys_ok",
                    "sequences_ok", "tenant_boundaries_ok"):
            with self.subTest(key=key):
                self.assertFalse(recovery_verified({**self.receipt, key: False}, self.now))
                self.assertFalse(recovery_verified({k:v for k,v in self.receipt.items() if k != key}, self.now))

    def test_live_restore_and_stale_receipt_refused(self):
        for patch in ({"isolation": "production"}, {"verified_at": "2026-10-10T00:00:00Z"},
                      {"verified_at": "2026-10-12T13:00:00Z"},
                      {"archive_sha256": "wrong"}, {"verified_at": "invalid"}):
            with self.subTest(patch=patch):
                self.assertFalse(recovery_verified({**self.receipt, **patch}, self.now))


if __name__ == "__main__":
    unittest.main()
