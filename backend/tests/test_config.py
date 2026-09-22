from __future__ import annotations

import importlib
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic_core import ValidationError

REQUIRED = {
    "DB_USER": "test-user",
    "DB_PASSWORD": "test-password-not-a-secret",
    "DB_HOST": "127.0.0.1",
    "DB_PORT": "1521",
    "DB_SERVICE_NAME": "TEST",
    "SECRET_KEY": "test-secret-key-not-for-production",
}


class SettingsContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original = {key: os.environ.get(key) for key in REQUIRED}
        sys.modules.pop("app.core.config", None)

    def tearDown(self) -> None:
        sys.modules.pop("app.core.config", None)
        for key, value in self.original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_missing_runtime_secrets_fail_closed(self) -> None:
        for key in REQUIRED:
            os.environ.pop(key, None)
        config = importlib.import_module("app.core.config")
        with self.assertRaises(ValidationError):
            config.build_settings()

    def test_explicit_runtime_values_are_accepted(self) -> None:
        os.environ.update(REQUIRED)
        config = importlib.import_module("app.core.config")
        self.assertEqual(config.settings.DB_USER, REQUIRED["DB_USER"])
        self.assertEqual(config.settings.DB_HOST, REQUIRED["DB_HOST"])
        self.assertEqual(config.settings.DB_PORT, 1521)


if __name__ == "__main__":
    unittest.main()
