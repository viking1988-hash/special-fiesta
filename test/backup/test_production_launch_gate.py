import unittest
from backup.production_launch_gate import evaluate, REQUIRED_EVIDENCE


class ProductionLaunchGateTests(unittest.TestCase):
    def test_missing_evidence_denies(self):
        result = evaluate({})
        self.assertEqual(result["status"], "NOT_AUTHORIZED")
        self.assertFalse(result["automated_launch_allowed"])
        self.assertEqual(set(result["missing_evidence"]), set(REQUIRED_EVIDENCE))

    def test_self_asserted_flags_do_not_authorize(self):
        result = evaluate({key: True for key in REQUIRED_EVIDENCE})
        self.assertEqual(result["status"], "NOT_AUTHORIZED")
        self.assertFalse(result["automated_launch_allowed"])
        self.assertTrue(result["manual_independent_verification_required"])

    def test_nonboolean_claims_not_accepted(self):
        result = evaluate({"production_launch_explicitly_approved": "YES"})
        self.assertIn("production_launch_explicitly_approved", result["missing_evidence"])

    def test_untrusted_payload_fails_closed(self):
        for value in (None, [], "approved"):
            with self.subTest(value=value):
                self.assertFalse(evaluate(value)["automated_launch_allowed"])


if __name__ == "__main__":
    unittest.main()
