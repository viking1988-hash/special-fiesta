import unittest
from datetime import datetime, timezone, timedelta
from backup.archive_metadata_gate import evaluate_backup_set, validate_archive


class ArchiveMetadataGateTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)
        self.good = {
            "name": "clients-20261012T110000Z.dump.age",
            "size": 12000,
            "sha256": "a" * 64,
            "type": "file",
        }

    def test_recent_private_archive(self):
        self.assertTrue(validate_archive(self.good, self.now))

    def test_stale_and_future_rejected(self):
        for name in ("clients-20261010T230000Z.dump.age", "clients-20261012T130000Z.dump.age"):
            with self.subTest(name=name):
                self.assertFalse(validate_archive({**self.good, "name": name}, self.now))

    def test_invalid_size_digest_or_public_access_rejected(self):
        for patch in ({"size": 0}, {"size": True}, {"sha256": "invalid"},
                      {"public_url": "https://example.invalid/"}, {"type": "dir"}):
            with self.subTest(patch=patch):
                self.assertFalse(validate_archive({**self.good, **patch}, self.now))

    def test_only_valid_archives_count(self):
        self.assertFalse(evaluate_backup_set([], self.now))
        self.assertFalse(evaluate_backup_set([{"name": "unrelated.txt"}], self.now))
        self.assertTrue(evaluate_backup_set([{"name": "unrelated.txt"}, self.good], self.now))


if __name__ == "__main__":
    unittest.main()
