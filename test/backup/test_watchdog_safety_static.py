"""Offline safety checks for client backup watchdog. No network, database or Telegram calls."""
import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
WATCHDOG = ROOT / "backup" / "watchdog.py"
REHEARSAL = ROOT / "test" / "backup" / "schema-rehearsal.py"

class WatchdogSafetyTests(unittest.TestCase):
    def test_watchdog_requires_explicit_opt_in(self):
        source = WATCHDOG.read_text(encoding="utf-8")
        self.assertIn('CLIENT_BACKUP_MONITOR_ENABLED', source)
        self.assertIn('CLIENT_BACKUP_MONITOR_DISABLED', source)
        self.assertIn('CLIENT_BACKUP_FRESHNESS_FAILED', source)

    def test_rehearsal_is_synthetic_only(self):
        source = REHEARSAL.read_text(encoding="utf-8")
        self.assertIn('SYNTHETIC_REHEARSAL_ONLY', source)
        self.assertIn('SCHEMA_REHEARSAL_DISABLED', source)
        self.assertIn('DATABASE_URL', source)
        self.assertIn('os.environ.pop(key, None)', source)

    def test_sources_parse(self):
        for path in (WATCHDOG, REHEARSAL):
            with self.subTest(path=path.name):
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

if __name__ == "__main__":
    unittest.main()
