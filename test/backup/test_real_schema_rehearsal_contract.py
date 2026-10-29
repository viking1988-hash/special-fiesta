"""Static guardrails for the separately gated real-schema rehearsal.

These tests do not execute the rehearsal or access any snapshot.
"""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
REHEARSAL = ROOT / "test/backup/schema-rehearsal.py"


class RealSchemaRehearsalContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = REHEARSAL.read_text(encoding="utf-8")

    def test_disabled_without_two_explicit_gates(self):
        self.assertIn('CLIENT_BACKUP_SCHEMA_REHEARSAL") != "true"', self.source)
        self.assertIn('SYNTHETIC_REHEARSAL_ONLY") != "YES"', self.source)

    def test_two_distinct_age_recipients_and_independent_decrypt(self):
        self.assertIn("AGE_RECIPIENT_PRIMARY=recipient", self.source)
        self.assertIn("AGE_RECIPIENT_RECOVERY=recovery_recipient", self.source)
        self.assertIn("if recipient == recovery_recipient:", self.source)
        self.assertIn('str(recovery_identity), "-o", os.devnull, str(encrypted)', self.source)

    def test_cluster_identity_bound_to_local_postgres(self):
        self.assertIn('CLIENT_BACKUP_EXPECTED_CLUSTER_ID=query("postgres", "SELECT system_identifier FROM pg_control_system()")', self.source)
        self.assertIn("CLIENT_BACKUP_EXPECTED_TEST_DB=target", self.source)

    def test_reviewed_schema_only_source_required_before_storage_access(self):
        self.assertIn("SCHEMA_ONLY_SOURCE_REVIEW_REQUIRED", self.source)
        self.assertIn('CLIENT_BACKUP_SCHEMA_ONLY_SOURCE_REVIEWED") != "YES"', self.source)
        self.assertLess(self.source.index("SCHEMA_ONLY_SOURCE_REVIEW_REQUIRED"), self.source.index('"get-object"'))

    def test_archive_contents_checked_before_restore(self):
        self.assertIn("SNAPSHOT_CONTAINS_DATA_REFUSED", self.source)
        self.assertIn("pg_restore", self.source)
        self.assertLess(self.source.index("SNAPSHOT_CONTAINS_DATA_REFUSED"), self.source.index("SCHEMA_ONLY_RESTORE_OK"))

    def test_required_client_tables_checked_before_schema_restore(self):
        self.assertIn("SNAPSHOT_REQUIRED_CLIENT_TABLE_MISSING", self.source)
        self.assertIn('for table in ("customers", "vehicles"):', self.source)
        self.assertLess(self.source.index("SNAPSHOT_REQUIRED_CLIENT_TABLE_MISSING"),
                        self.source.index("SCHEMA_ONLY_RESTORE_OK"))

    def test_explicit_schema_only_object_selection(self):
        self.assertIn("CLIENT_BACKUP_SCHEMA_ONLY_OBJECT_KEY", self.source)
        self.assertIn("SCHEMA_ONLY_OBJECT_KEY_REQUIRED", self.source)
        self.assertIn("crm-schema-only-", self.source)
        self.assertIn('x["Key"] == reviewed_key', self.source)
        self.assertNotIn('"--prefix", "crm-"', self.source)

    def test_rehearsal_gate_is_enforced_before_any_subprocess(self):
        import os
        import runpy
        from unittest.mock import patch

        with patch.dict(os.environ, {
            "CLIENT_BACKUP_SCHEMA_REHEARSAL": "true",
            "SYNTHETIC_REHEARSAL_ONLY": "YES",
            "CLIENT_BACKUP_SCHEMA_ONLY_SOURCE_REVIEWED": "NO",
        }):
            with patch("subprocess.run", side_effect=AssertionError("unexpected subprocess")):
                with self.assertRaises(SystemExit) as exit_context:
                    runpy.run_path(str(REHEARSAL), run_name="__main__")
                self.assertEqual(exit_context.exception.code, 1)

    def test_pinned_schema_archive_digest_required(self):
        self.assertIn("CLIENT_BACKUP_SCHEMA_ONLY_SHA256", self.source)
        self.assertIn("SCHEMA_ONLY_EXPECTED_SHA256_REQUIRED", self.source)
        self.assertIn("SCHEMA_ONLY_SHA256_MISMATCH", self.source)
        self.assertLess(self.source.index("SCHEMA_ONLY_EXPECTED_SHA256_REQUIRED"), self.source.index('"get-object"'))
        self.assertLess(self.source.index("SCHEMA_ONLY_SHA256_MISMATCH"), self.source.index('"pg_restore", "--list"'))

    def test_selector_preflight_precedes_storage_listing(self):
        self.assertIn("validator.validate_schema_source(", self.source)
        self.assertLess(self.source.index("validator.validate_schema_source("), self.source.index('"list-objects-v2"'))

    def test_schema_only_and_artificial_records(self):
        self.assertIn('"--schema-only"', self.source)
        self.assertIn("ARTIFICIAL ONE", self.source)
        self.assertIn("REAL_SCHEMA_ROW_DIGEST_MISMATCH", self.source)


if __name__ == "__main__":
    unittest.main()
