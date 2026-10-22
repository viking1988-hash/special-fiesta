import tempfile
import unittest
from pathlib import Path
from backup.live_output_gate import validate


class LiveOutputGateTests(unittest.TestCase):
    def test_private_unused_archive_allowed(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "clients-20261012T120000Z.dump.age"
            self.assertTrue(validate(d, str(p)))

    def test_relative_and_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(validate(d, "clients-20261012T120000Z.dump.age"))
            self.assertFalse(validate(d, str(Path(d) / ".." / "clients-20261012T120000Z.dump.age")))

    def test_normalizing_parent_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            filename = "clients-20261012T120000Z.dump.age"
            # Both paths resolve to the same private directory, but the
            # caller supplied a lexical parent traversal and must be refused.
            target = str(root / "nested" / ".." / filename)
            self.assertFalse(validate(d, target))
            self.assertFalse(validate(str(root / "nested" / ".."), str(root / filename)))

    def test_wrong_prefix_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "archive-20261012T120000Z.dump.age"
            self.assertFalse(validate(d, str(p)))

    def test_impossible_calendar_timestamp_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            for stamp in ("20260230T120000Z", "20261301T120000Z", "20261012T256100Z"):
                with self.subTest(stamp=stamp):
                    p = Path(d) / f"clients-{stamp}.dump.age"
                    self.assertFalse(validate(d, str(p)))

    def test_existing_file_and_partial_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "clients-20261012T120000Z.dump.age"
            p.touch()
            self.assertFalse(validate(d, str(p)))
            p.unlink()
            Path(str(p) + ".partial").touch()
            self.assertFalse(validate(d, str(p)))

    def test_dangling_partial_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "clients-20261012T120000Z.dump.age"
            Path(str(p) + ".partial").symlink_to(Path(d) / "missing-target")
            self.assertFalse(validate(d, str(p)))

    def test_symlinked_parent_directory_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            private = base / "private"
            private.mkdir(mode=0o700)
            alias = base / "alias"
            alias.symlink_to(private, target_is_directory=True)
            nested = alias / "nested"
            nested.mkdir(mode=0o700)
            p = nested / "clients-20261012T120000Z.dump.age"
            self.assertFalse(validate(str(nested), str(p)))

    def test_public_directory_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "clients-20261012T120000Z.dump.age"
            Path(d).chmod(0o755)
            self.assertFalse(validate(d, str(p)))

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "clients-20261012T120000Z.dump.age"
            target = Path(d) / "real"
            target.touch()
            p.symlink_to(target)
            self.assertFalse(validate(d, str(p)))


if __name__ == "__main__":
    unittest.main()
