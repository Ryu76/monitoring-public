import importlib
import os
import ast
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

@pytest.fixture(autouse=True)
def restore_config():
    import app.core.config as config
    original_environ = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_environ)
    # Mock load_encrypted_env to avoid looking for files during reload
    with patch('app.core.config.load_encrypted_env', return_value={}):
        importlib.reload(config)

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

        override_values = required_test_values.copy()
        override_values["DB_USER"] = "override_user"

        with patch.dict(os.environ, override_values, clear=True):
            import app.core.config as config
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
    from app.core.config import Settings
    fields = Settings.model_fields
    db_password_field = fields['DB_PASSWORD']
    assert db_password_field.default in (None, ..., Ellipsis) or not db_password_field.is_required() == False

def test_source_level_checks_for_echo_and_credentials():
    # Ensure database engine is never created with echo=True
    db_file_path = Path(__file__).resolve().parents[1] / "app" / "core" / "database.py"
    db_source = db_file_path.read_text(encoding="utf-8")

    class CreateEngineVisitor(ast.NodeVisitor):
        def __init__(self):
            self.echo_found = False
            self.echo_value = None

        def visit_Call(self, node):
            if isinstance(node.func, ast.Name) and node.func.id == "create_engine":
                for kw in node.keywords:
                    if kw.arg == "echo":
                        self.echo_found = True
                        if isinstance(kw.value, ast.Constant):
                            self.echo_value = kw.value.value
            self.generic_visit(node)

    visitor = CreateEngineVisitor()
    visitor.visit(ast.parse(db_source))

    # Must be either explicitly echo=False or omitted (defaults to False)
    if visitor.echo_found:
        assert visitor.echo_value is False, "SQL echo must not be enabled (echo=True) in database.py"
