from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from cryptography.fernet import Fernet

from app.core.dpapi import protect_data
import preflight

REQUIRED_TEST_VALUES = {
    "DB_USER": "test_user",
    "DB_PASSWORD": "test_password",
    "DB_HOST": "database.internal.example",
    "DB_PORT": "1521",
    "DB_SERVICE_NAME": "test_service",
    "DB_SCHEMA": "TEST_SCHEMA",
    "SECRET_KEY": "test_secret",
}


def _write_artifacts(directory: Path, values: dict[str, str] = REQUIRED_TEST_VALUES) -> None:
    fernet_key = Fernet.generate_key()
    payload = "\n".join(f"{key}={value}" for key, value in values.items())
    (directory / ".env.enc").write_bytes(Fernet(fernet_key).encrypt(payload.encode("utf-8")))
    (directory / "env.key.dpapi").write_bytes(protect_data(fernet_key))


def test_preflight_missing_artifacts(capsys):
    with TemporaryDirectory() as temp_dir:
        assert preflight.run_preflight(backend_dir=Path(temp_dir)) is False
    assert "[FAIL] Missing .env.enc" in capsys.readouterr().out


def test_preflight_rejects_invalid_schema_without_connecting(capsys):
    with TemporaryDirectory() as temp_dir:
        directory = Path(temp_dir)
        invalid_values = {**REQUIRED_TEST_VALUES, "DB_SCHEMA": "INVALID-SCHEMA"}
        _write_artifacts(directory, invalid_values)
        assert preflight.run_preflight(backend_dir=directory) is False
    output = capsys.readouterr().out
    assert "Configuration validation failed" in output
    assert "INVALID-SCHEMA" not in output


def test_preflight_runs_read_only_schema_mapped_checks_without_leaking_values(capsys):
    with TemporaryDirectory() as temp_dir:
        directory = Path(temp_dir)
        _write_artifacts(directory)

        mock_engine = MagicMock()
        mock_session_factory = MagicMock()
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session
        core_rows = MagicMock()
        core_rows.scalars.return_value.all.return_value = list(preflight.CORE_TABLES)
        mock_session.execute.side_effect = [MagicMock(), core_rows, MagicMock()]

        with patch("app.core.database.create_database_engine", return_value=mock_engine) as factory, patch(
            "preflight.sessionmaker", return_value=mock_session_factory
        ):
            assert preflight.run_preflight(backend_dir=directory) is True

        assert factory.call_args.kwargs["db_schema"] == "TEST_SCHEMA"
        statements = [str(call.args[0]) for call in mock_session.execute.call_args_list]
        assert "SELECT 1 FROM DUAL" in statements[0]
        assert "all_tables" in statements[1]
        assert "sys_user" in statements[2].lower()
        assert mock_session.rollback.call_count == 1
        assert mock_session.close.call_count == 1

    output = capsys.readouterr().out
    assert "Database read-only preflight completed" in output
    for secret_or_endpoint in ("test_password", "test_user", "database.internal.example", "test_service", "oracle+oracledb://"):
        assert secret_or_endpoint not in output


def test_preflight_suppresses_database_exception_details(capsys):
    with TemporaryDirectory() as temp_dir:
        directory = Path(temp_dir)
        _write_artifacts(directory)
        with patch("app.core.database.create_database_engine", side_effect=Exception("Database down")):
            assert preflight.run_preflight(backend_dir=directory) is False
    output = capsys.readouterr().out
    assert "Database read-only preflight failed" in output
    assert "Database down" not in output
    assert "Traceback" not in output
