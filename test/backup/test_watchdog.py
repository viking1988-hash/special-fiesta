import datetime as dt
import importlib.util
import io
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parents[2] / 'backup'))
import watchdog as w


class WatchdogTests(unittest.TestCase):
    def test_disabled_has_no_network(self):
        factory = Mock()
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(w.main(factory), 0)
        factory.assert_not_called()

    def test_fresh_never_notifies(self):
        factory = Mock()
        with patch.dict(os.environ, {'CLIENT_BACKUP_MONITOR_ENABLED': 'true'}, clear=True), patch.object(w.notify, 'main') as notify:
            self.assertEqual(w.main(factory), 0)
            notify.assert_not_called()

    def test_missing_keeps_failure_and_notifies(self):
        factory = Mock()
        factory.return_value.check_freshness.side_effect = ValueError('secret raw provider error')
        with patch.dict(os.environ, {'CLIENT_BACKUP_MONITOR_ENABLED': 'true'}, clear=True), patch.object(w.notify, 'main') as notify, patch('sys.stderr', new_callable=io.StringIO) as log:
            self.assertEqual(w.main(factory), 1)
            notify.assert_called_once_with(reason='missing')
            self.assertNotIn('secret', log.getvalue())

    def test_notification_failure_preserves_monitor_failure(self):
        factory = Mock(side_effect=ValueError('secret'))
        with patch.dict(os.environ, {'CLIENT_BACKUP_MONITOR_ENABLED': 'true'}, clear=True), patch.object(w.notify, 'main', side_effect=ValueError('token')), patch('sys.stderr', new_callable=io.StringIO) as log:
            self.assertEqual(w.main(factory), 1)
            self.assertIn('CLIENT_BACKUP_ALERT_FAILED', log.getvalue())
            self.assertNotIn('token', log.getvalue())
