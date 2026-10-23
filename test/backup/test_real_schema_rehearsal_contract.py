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

    def test_schema_only_and_artificial_records(self):
        self.assertIn('"--schema-only"', self.source)
        self.assertIn("ARTIFICIAL ONE", self.source)
        self.assertIn("REAL_SCHEMA_ROW_DIGEST_MISMATCH", self.source)


if __name__ == "__main__":
    unittest.main()
