"""Offline safety checks for client backup watchdog. No network, database or Telegram calls."""
import ast
import importlib.util
import os
import sys
from unittest import mock
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

    def load_watchdog(self):
        # Import with synthetic dependencies: never import network clients.
        fake_yandex = mock.Mock()
        fake_notify = mock.Mock()
        with mock.patch.dict(sys.modules, {"yandex": fake_yandex, "notify": fake_notify}):
            spec = importlib.util.spec_from_file_location("isolated_backup_watchdog", WATCHDOG)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        return module, fake_notify

    def test_disabled_watchdog_never_contacts_disk(self):
        module, notify = self.load_watchdog()
        disk = mock.Mock()
        with mock.patch.dict(os.environ, {"CLIENT_BACKUP_MONITOR_ENABLED": "false"}):
            self.assertEqual(module.main(disk_factory=disk), 0)
        disk.assert_not_called()
        notify.main.assert_not_called()

    def test_healthy_watchdog_does_not_alert(self):
        module, notify = self.load_watchdog()
        disk = mock.Mock()
        with mock.patch.dict(os.environ, {"CLIENT_BACKUP_MONITOR_ENABLED": "true"}):
            self.assertEqual(module.main(disk_factory=disk), 0)
        disk.return_value.check_freshness.assert_called_once_with(None)
        notify.main.assert_not_called()

    def test_failed_freshness_triggers_alert_and_failure(self):
        module, notify = self.load_watchdog()
        disk = mock.Mock()
        disk.return_value.check_freshness.side_effect = RuntimeError("synthetic")
        with mock.patch.dict(os.environ, {"CLIENT_BACKUP_MONITOR_ENABLED": "true"}):
            self.assertEqual(module.main(disk_factory=disk), 1)
        notify.main.assert_called_once_with(reason="missing")

    def test_alert_failure_still_fails_closed(self):
        module, notify = self.load_watchdog()
        disk = mock.Mock()
        disk.return_value.check_freshness.side_effect = RuntimeError("synthetic")
        notify.main.side_effect = RuntimeError("synthetic")
        with mock.patch.dict(os.environ, {"CLIENT_BACKUP_MONITOR_ENABLED": "true"}):
            self.assertEqual(module.main(disk_factory=disk), 1)

    def test_sources_parse(self):
        for path in (WATCHDOG, REHEARSAL):
            with self.subTest(path=path.name):
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

if __name__ == "__main__":
    unittest.main()
