import importlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.core.dpapi import protect_data

required_test_values = {
    "DB_USER": "test_user",
    "DB_PASSWORD": "test_password",
    "DB_HOST": "localhost",
    "DB_PORT": "1521",
    "DB_SERVICE_NAME": "test_service",
    "SECRET_KEY": "test_secret_key",
}

def test_dpapi_encrypted_env_round_trip():
    with TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        env_enc_path = temp_dir_path / ".env.enc"
        key_dpapi_path = temp_dir_path / "env.key.dpapi"
        env_payload = "\n".join(f"{key}={value}" for key, value in required_test_values.items())

        fernet_key = Fernet.generate_key()
        encrypted_env = Fernet(fernet_key).encrypt(env_payload.encode("utf-8"))
        dpapi_key = protect_data(fernet_key)
        env_enc_path.write_bytes(encrypted_env)
        key_dpapi_path.write_bytes(dpapi_key)

        from app.core import config
        env_vars = config.load_encrypted_env(
            env_path=str(env_enc_path),
            key_path=str(key_dpapi_path),
        )

        assert env_vars == required_test_values

def test_host_environment_priority():
    # Test that OS env vars have priority over encrypted env
    with TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        env_enc_path = temp_dir_path / ".env.enc"
        key_dpapi_path = temp_dir_path / "env.key.dpapi"
        env_payload = "\n".join(f"{key}={value}" for key, value in required_test_values.items())

        fernet_key = Fernet.generate_key()
        encrypted_env = Fernet(fernet_key).encrypt(env_payload.encode("utf-8"))
        dpapi_key = protect_data(fernet_key)
        env_enc_path.write_bytes(encrypted_env)
        key_dpapi_path.write_bytes(dpapi_key)

        # Set DB_USER in OS environment to something else
        override_values = required_test_values.copy()
        override_values["DB_USER"] = "override_user"

        with patch.dict(os.environ, override_values, clear=True):
            import app.core.config as config
            # We mock the path in config loading if we needed, but load_encrypted_env just returns dict.
            # In Settings class, it should respect OS env.
            env_vars = config.load_encrypted_env(
                env_path=str(env_enc_path),
                key_path=str(key_dpapi_path),
            )
            # The manual dict from file shouldn't change, but Settings should override.
            # Let's test Pydantic settings loading.

            with patch('app.core.config.load_encrypted_env', return_value=required_test_values):
                importlib.reload(config)
                assert config.settings.DB_USER == "override_user"
                assert config.settings.DB_PASSWORD == "test_password"

def test_missing_required_secret_fail_closed():
    # If a required secret is missing, it should fail to load (ValidationError)
    incomplete_values = {k: v for k, v in required_test_values.items() if k != "DB_PASSWORD"}
    with patch.dict(os.environ, incomplete_values, clear=True):
        import app.core.config as config
        with patch('app.core.config.load_encrypted_env', return_value={}):
            with pytest.raises(ValidationError):
                importlib.reload(config)

def test_no_unsafe_sql_secret_fallback():
    # Ensure there's no unsafe fallback if the config doesn't provide a DB_PASSWORD
    # i.e., it doesn't default to something easily guessable or blank for prod.
    # We can check the model fields to ensure it has no default for DB_PASSWORD.
    from app.core.config import Settings
    fields = Settings.__fields__ if hasattr(Settings, '__fields__') else Settings.model_fields
    db_password_field = fields['DB_PASSWORD']
    # Ensure no default is set
    assert db_password_field.default in (None, ..., Ellipsis) or not db_password_field.is_required() == False
