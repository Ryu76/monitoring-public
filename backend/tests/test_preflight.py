import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock
import pytest
from cryptography.fernet import Fernet

from app.core.dpapi import protect_data
import preflight

required_test_values = {
    "DB_USER": "test_user",
    "DB_PASSWORD": "test_password",
    "DB_HOST": "localhost",
    "DB_PORT": "1521",
    "DB_SERVICE_NAME": "test_service",
    "SECRET_KEY": "test_secret",
}

def test_preflight_missing_artifacts(capsys):
    with TemporaryDirectory() as temp_dir:
        success = preflight.run_preflight(backend_dir=Path(temp_dir))
        assert success is False
        captured = capsys.readouterr()
        assert "[FAIL] Missing .env.enc" in captured.out

def test_preflight_decryptability_failure(capsys):
    with TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        env_enc_path = temp_dir_path / ".env.enc"
        key_dpapi_path = temp_dir_path / "env.key.dpapi"

        env_enc_path.write_bytes(b"invalid_encrypted_data")
        key_dpapi_path.write_bytes(b"invalid_dpapi_key")

        success = preflight.run_preflight(backend_dir=temp_dir_path)
        assert success is False
        captured = capsys.readouterr()
        assert "[FAIL]" in captured.out
        # Should not leak raw exceptions
        assert "Traceback" not in captured.out

def test_preflight_success(capsys):
    with TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        env_enc_path = temp_dir_path / ".env.enc"
        key_dpapi_path = temp_dir_path / "env.key.dpapi"

        env_payload = "\n".join(f"{k}={v}" for k, v in required_test_values.items())
        fernet_key = Fernet.generate_key()
        encrypted_env = Fernet(fernet_key).encrypt(env_payload.encode("utf-8"))
        dpapi_key = protect_data(fernet_key)

        env_enc_path.write_bytes(encrypted_env)
        key_dpapi_path.write_bytes(dpapi_key)

        # Mock database connection
        mock_engine = MagicMock()
        mock_session_maker = MagicMock()
        mock_session = MagicMock()
        mock_session_maker.return_value = mock_session

        with patch("preflight.create_engine", return_value=mock_engine) as mock_create_engine, \
             patch("preflight.sessionmaker", return_value=mock_session_maker):

            success = preflight.run_preflight(backend_dir=temp_dir_path)

            assert success is True

            # Verify DB connection read-only and rollback
            mock_session.execute.assert_called_once()
            args, _ = mock_session.execute.call_args
            assert "SELECT 1 FROM DUAL" in str(args[0])
            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()

            # Verify connection string didn't have echo=True
            assert mock_create_engine.call_args.kwargs.get("echo") is False

            captured = capsys.readouterr()
            assert "[OK] Encrypted configuration artifacts found" in captured.out
            assert "[OK] Configuration successfully decrypted" in captured.out
            assert "[INFO] Target DB Endpoint: localhost:1521 (Service: test_service)" in captured.out
            assert "[OK] Database connection and read test successful" in captured.out

            # Ensure no secrets printed
            assert "test_password" not in captured.out
            assert "test_user" not in captured.out
            assert "oracle+oracledb://" not in captured.out

def test_preflight_db_connection_failure(capsys):
    with TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        env_enc_path = temp_dir_path / ".env.enc"
        key_dpapi_path = temp_dir_path / "env.key.dpapi"

        env_payload = "\n".join(f"{k}={v}" for k, v in required_test_values.items())
        fernet_key = Fernet.generate_key()
        encrypted_env = Fernet(fernet_key).encrypt(env_payload.encode("utf-8"))
        dpapi_key = protect_data(fernet_key)

        env_enc_path.write_bytes(encrypted_env)
        key_dpapi_path.write_bytes(dpapi_key)

        with patch("preflight.create_engine", side_effect=Exception("Database down")):
            success = preflight.run_preflight(backend_dir=temp_dir_path)

            assert success is False
            captured = capsys.readouterr()
            assert "[FAIL] Database connection failed" in captured.out
            assert "Database down" not in captured.out
            assert "Traceback" not in captured.out
