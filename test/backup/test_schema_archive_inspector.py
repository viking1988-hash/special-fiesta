"""Offline tests of the schema-only archive inspector; no PostgreSQL needed."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "inspect-schema-only-archive.py"
spec = importlib.util.spec_from_file_location("schema_archive_inspector", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SchemaArchiveInspectorTests(unittest.TestCase):
    def test_rejects_data_toc(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "sample.dump"
            archive.write_bytes(b"PGDMP" + b"0" * 2048)
            toc = "123; 0 456 TABLE DATA public customers postgres\n"
            with patch.object(module.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, toc, "")):
                with self.assertRaisesRegex(ValueError, "ARCHIVE_CONTAINS_DATA_REFUSED"):
                    module.inspect(archive)

    def test_accepts_schema_toc_and_reports_digest(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "sample.dump"
            archive.write_bytes(b"PGDMP" + b"0" * 2048)
            toc = "123; 0 456 TABLE public customers postgres\n"
            with patch.object(module.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, toc, "")):
                output = module.inspect(archive)
            self.assertIn("SCHEMA_ONLY_TOC_PASS", output)
            self.assertIn("sha256=", output)

    def test_rejects_bad_magic_without_invoking_pg_restore(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "sample.dump"
            archive.write_bytes(b"BAD!!" + b"0" * 2048)
            with patch.object(module.subprocess, "run") as runner:
                with self.assertRaisesRegex(ValueError, "ARCHIVE_FORMAT_REFUSED"):
                    module.inspect(archive)
                runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
