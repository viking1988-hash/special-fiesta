"""Guard the documented client-only export scope against accidental widening.

This static check reads the export command only. It does not access PostgreSQL
or customer data and does not certify a standalone recoverable backup.
"""
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXPORTER = ROOT / "scripts" / "crm-clients-export.sh"
DOC = ROOT / "docs" / "client-backup-data-completeness-and-go-no-go.md"


class ClientExportScopeTests(unittest.TestCase):
    def test_explicit_table_allowlist_is_exact(self):
        source = EXPORTER.read_text(encoding="utf-8")
        tables = re.findall(r"--table=(\S+)", source)
        self.assertEqual(tables, ["public.customers", "public.vehicles"])
        self.assertIn("--data-only", source)
        self.assertIn("--format=custom", source)
        self.assertNotIn("--schema-only", source)

    def test_no_full_recovery_claim_in_scope_document(self):
        doc = DOC.read_text(encoding="utf-8")
        self.assertIn("NO-GO", doc)
        self.assertIn("not a standalone full CRM recovery point", doc)
        self.assertIn("Do not merge PR #12", doc)


if __name__ == "__main__":
    unittest.main()
