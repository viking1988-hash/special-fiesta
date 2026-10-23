import unittest
from backup.live_export_preflight import check


class LiveExportPreflightTests(unittest.TestCase):
    def setUp(self):
        self.valid = {
            "DATABASE_URL": "postgresql://crm_clients_backup_reader:placeholder@db.internal:5432/crm",
            "AGE_RECIPIENT_PRIMARY": "age1" + "q" * 58,
            "AGE_RECIPIENT_RECOVERY": "age1" + "p" * 58,
            "YANDEX_DISK_TOKEN": "test-token",
            "CLIENT_BACKUP_YANDEX_PATH": "app:/clients-backups",
            "CLIENT_BACKUP_ENABLED": "true",
            "CLIENT_BACKUP_REQUIRE_ENCRYPTION": "true",
            "CLIENT_BACKUP_SCHEMA_VERIFIED": "YES",
            "CLIENT_BACKUP_READER_ACL_VERIFIED": "YES",
            "CLIENT_BACKUP_RECOVERY_KEY_OFFLINE": "YES",
        }

    def test_valid_configuration(self):
        self.assertEqual(check(self.valid), [])

    def test_missing_credentials_fails_closed(self):
        for key in ("DATABASE_URL", "AGE_RECIPIENT_PRIMARY", "AGE_RECIPIENT_RECOVERY", "YANDEX_DISK_TOKEN"):
            with self.subTest(key=key):
                config = dict(self.valid)
                config.pop(key)
                self.assertTrue(check(config))

    def test_duplicate_recipients_rejected(self):
        config = dict(self.valid)
        config["AGE_RECIPIENT_RECOVERY"] = config["AGE_RECIPIENT_PRIMARY"]
        self.assertIn("AGE_RECIPIENTS_NOT_DISTINCT", check(config))

    def test_invalid_recovery_recipient_rejected(self):
        config = dict(self.valid)
        config["AGE_RECIPIENT_RECOVERY"] = "not-an-age-recipient"
        self.assertIn("INVALID_AGE_RECIPIENT_RECOVERY", check(config))

    def test_privileged_role_rejected(self):
        config = dict(self.valid)
        config["DATABASE_URL"] = "postgresql://postgres:pw@db.internal/crm"
        self.assertIn("PRIVILEGED_DATABASE_ROLE_REFUSED", check(config))

    def test_ambiguous_database_url_rejected(self):
        for url in (
            "postgresql://crm_clients_backup_reader@db.internal/crm",
            "postgresql://crm_clients_backup_reader:placeholder@db.internal/crm#ignored",
            "postgresql://crm_clients_backup_reader:placeholder@db.internal/crm?options=-c%20search_path%3Dpublic",
        ):
            with self.subTest(url=url):
                config = dict(self.valid)
                config["DATABASE_URL"] = url
                self.assertIn("INVALID_DATABASE_URL", check(config))

    def test_plaintext_or_unverified_schema_rejected(self):
        for key, value in (
            ("CLIENT_BACKUP_REQUIRE_ENCRYPTION", "false"),
            ("CLIENT_BACKUP_SCHEMA_VERIFIED", "NO"),
            ("CLIENT_BACKUP_READER_ACL_VERIFIED", "NO"),
            ("CLIENT_BACKUP_RECOVERY_KEY_OFFLINE", "NO"),
        ):
            with self.subTest(key=key):
                config = dict(self.valid)
                config[key] = value
                self.assertTrue(check(config))

    def test_test_mode_and_wrong_destination_rejected(self):
        config = dict(self.valid)
        config["SYNTHETIC_REHEARSAL_ONLY"] = "YES"
        config["CLIENT_BACKUP_YANDEX_PATH"] = "app:/clients-backups-test"
        errors = check(config)
        self.assertIn("SYNTHETIC_MODE_NOT_LIVE", errors)
        self.assertIn("DESTINATION_NOT_APPROVED", errors)


if __name__ == "__main__":
    unittest.main()
