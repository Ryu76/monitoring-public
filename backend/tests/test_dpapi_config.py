import importlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

from app.core.dpapi import protect_data

required_test_values = {
    "DB_USER": "test_user",
    "DB_PASSWORD": "test_password",
    "DB_HOST": "localhost",
    "DB_PORT": "1521",
    "DB_SERVICE_NAME": "test_service",
    "SECRET_KEY": "test_secret_key",
}

@pytest.fixture(autouse=True)
def restore_config():
    import app.core.config as config
    original_environ = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_environ)
    with patch('app.core.config.load_encrypted_env', return_value={}):
        importlib.reload(config)

def test_load_encrypted_env():
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

        with patch.dict(os.environ, required_test_values, clear=False):
            from app.core import config

            importlib.reload(config)
            env_vars = config.load_encrypted_env(
                env_path=str(env_enc_path),
                key_path=str(key_dpapi_path),
            )

        assert env_vars == required_test_values


def test_settings_requires_env_vars():
    with patch.dict(os.environ, {}, clear=True):
        from app.core import config
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            config.build_settings()


def test_settings_loaded_with_env_vars():
    with patch.dict(os.environ, required_test_values, clear=False):
        import app.core.config as config

        importlib.reload(config)
        assert config.settings.DB_USER == "test_user"


def test_load_encrypted_env_invalid_paths():
    with patch.dict(os.environ, required_test_values, clear=False):
        from app.core import config

        importlib.reload(config)
        env_vars = config.load_encrypted_env(
            env_path="nonexistent.enc",
            key_path="nonexistent.dpapi",
        )

    assert env_vars == {}
