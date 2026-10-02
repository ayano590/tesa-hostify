import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import config


class ConfigValidationTests(unittest.TestCase):
    def setUp(self):
        self.config_values = {
            "READ_API_TOKEN": "a" * 32,
            "TESA_USERNAME": "tesa-user",
            "TESA_PASSWORD": "secret-password",
            "TTLOCK_CLIENT_ID": "client-id",
            "TTLOCK_CLIENT_SECRET": "client-secret",
            "TTLOCK_USERNAME": "ttlock-user",
            "TTLOCK_PASSWORD_MD5": "password-hash",
            "TTLOCK_ROOM2_LOCK_ID": "lock-2",
            "TTLOCK_ROOM2_PWD_ID": "password-2",
            "TTLOCK_ROOM6_LOCK_ID": "lock-6",
            "TTLOCK_ROOM6_PWD_ID": "password-6",
            "TESA_BASE_URL": None,
            "TTLOCK_BASE_URL": None,
        }
        self.config_patch = patch.multiple(config, **self.config_values)
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)
        self.env_patch = patch.dict(os.environ, {}, clear=True)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def test_accepts_complete_credentials_and_optional_default_urls(self):
        config.validate_config()

    def test_reports_missing_variables_without_revealing_secret_values(self):
        with patch.multiple(
            config,
            TESA_PASSWORD=None,
            TTLOCK_CLIENT_SECRET=None,
            TTLOCK_ROOM2_PWD_ID=" ",
        ):
            with self.assertRaisesRegex(ValueError, "TESA_PASSWORD") as raised:
                config.validate_config()

        message = str(raised.exception)
        self.assertIn("TTLOCK_CLIENT_SECRET", message)
        self.assertIn("TTLOCK_ROOM2_PWD_ID", message)
        self.assertNotIn("secret-password", message)
        self.assertNotIn("client-secret", message)


    def test_rejects_invalid_base_url(self):
        with patch.object(config, "TTLOCK_BASE_URL", "ftp://lock.example"):
            with self.assertRaisesRegex(ValueError, "TTLOCK_BASE_URL"):
                config.validate_config()

    def test_rejects_invalid_tls_boolean_setting(self):
        with patch.dict(os.environ, {"TESA_VERIFY_SSL": "sometimes"}):
            with self.assertRaisesRegex(ValueError, "TESA_VERIFY_SSL"):
                config.validate_config()

    def test_rejects_short_read_api_token(self):
        with patch.object(config, "READ_API_TOKEN", "too-short"):
            with self.assertRaisesRegex(ValueError, "READ_API_TOKEN"):
                config.validate_config()

    def test_accepts_valid_tls_boolean_setting(self):
        with patch.dict(os.environ, {"TESA_VERIFY_SSL": "true", "TTLOCK_VERIFY_SSL": "0"}):
            config.validate_config()


if __name__ == "__main__":
    unittest.main()
