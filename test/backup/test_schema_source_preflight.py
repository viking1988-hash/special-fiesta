"""Offline unit tests for schema-only source selector. No network or database."""
import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).with_name("schema_source_preflight.py")
spec = importlib.util.spec_from_file_location("schema_source_preflight", MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SchemaSourcePreflightTests(unittest.TestCase):
    def test_valid_selector(self):
        key = "crm-schema-only-20261023-120000.dump"
        self.assertEqual(module.validate_schema_source(key, "AB" * 32), (key, "ab" * 32))

    def test_generic_full_backup_rejected(self):
        with self.assertRaisesRegex(ValueError, "SCHEMA_ONLY_OBJECT_KEY_REQUIRED"):
            module.validate_schema_source("crm-20261023-120000.dump", "ab" * 32)

    def test_prefix_and_traversal_rejected(self):
        for key in ("../crm-schema-only-20261023-120000.dump", "crm-schema-only-20261023-120000.dump/other"):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    module.validate_schema_source(key, "ab" * 32)

    def test_missing_or_invalid_hash_rejected(self):
        for digest in ("", "0" * 63, "z" * 64):
            with self.subTest(digest=digest):
                with self.assertRaisesRegex(ValueError, "SCHEMA_ONLY_EXPECTED_SHA256_REQUIRED"):
                    module.validate_schema_source("crm-schema-only-20261023-120000.dump", digest)


if __name__ == "__main__":
    unittest.main()
