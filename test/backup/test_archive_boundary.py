"""Tests for archive validator boundary cases. Synthetic metadata only."""
import unittest
from datetime import datetime, timezone, timedelta
from backup.archive_metadata_gate import validate_archive


class ArchiveBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)
        self.good = {"name": "clients-20261012T110000Z.dump.age",
                     "size": 4096, "sha256": "f" * 64, "type": "file"}

    def test_exact_36_hour_boundary_allowed(self):
        self.assertTrue(validate_archive(
            {**self.good, "name": "clients-20261011T000000Z.dump.age"}, self.now))

    def test_over_36_hours_refused(self):
        self.assertFalse(validate_archive(
            {**self.good, "name": "clients-20261010T235959Z.dump.age"}, self.now))

    def test_exact_current_time_allowed(self):
        self.assertTrue(validate_archive(
            {**self.good, "name": "clients-20261012T120000Z.dump.age"}, self.now))

    def test_bad_dates_and_digest_case_refused(self):
        for patch in ({"name": "clients-20260230T120000Z.dump.age"},
                      {"name": "clients-20261012T120000Z.dump"},
                      {"sha256": "F" * 64}):
            with self.subTest(patch=patch):
                self.assertFalse(validate_archive({**self.good, **patch}, self.now))

    def test_boolean_size_and_oversize_refused(self):
        for size in (True, False, -1, 2 * 1024**3 + 1):
            with self.subTest(size=size):
                self.assertFalse(validate_archive({**self.good, "size": size}, self.now))


if __name__ == "__main__":
    unittest.main()
