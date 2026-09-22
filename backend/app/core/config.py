from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from cryptography.fernet import Fernet
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

from app.core.dpapi import unprotect_data


def load_encrypted_env(env_path: str | None = None, key_path: str | None = None) -> dict[str, str]:
    """Load DPAPI-protected local development settings without logging values."""
    backend_dir = Path(__file__).resolve().parents[2]
    encrypted_path = Path(env_path) if env_path else backend_dir / ".env.enc"
    protected_key_path = Path(key_path) if key_path else backend_dir / "env.key.dpapi"
    if not encrypted_path.is_file() or not protected_key_path.is_file():
        return {}

    try:
        fernet_key = unprotect_data(protected_key_path.read_bytes())
        if not fernet_key:
            return {}
        decrypted_data = Fernet(fernet_key).decrypt(encrypted_path.read_bytes()).decode("utf-8")
    except Exception:
        return {}

    values: dict[str, str] = {}
    for line in decrypted_data.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


class Settings(BaseSettings):
    """Required runtime configuration. No database or JWT secret has a source fallback."""

    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: int
    DB_SERVICE_NAME: str
    DB_SCHEMA: str = Field(
        default="example_db_user",
        pattern=r"^[A-Za-z][A-Za-z0-9_$#]{0,127}$",
        description="Oracle schema identifier used for schema-less ORM tables.",
    )
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    model_config = SettingsConfigDict(case_sensitive=True)


def build_settings(values: Mapping[str, str] | None = None) -> Settings:
    """Build settings from explicit values and the process environment.

    Explicit values win in ``BaseSettings``.  ``load_runtime_settings`` supplies
    encrypted values only for keys absent from the process environment, so host
    values remain authoritative without changing ``os.environ`` during import.
    """
    return Settings(**dict(values or {}))


_runtime_settings: Settings | None = None


def load_runtime_settings(
    env_path: str | None = None,
    key_path: str | None = None,
) -> Settings:
    """Explicitly load optional encrypted development settings for an app process."""
    encrypted_values = load_encrypted_env(env_path=env_path, key_path=key_path)
    fallback_values = {
        key: value for key, value in encrypted_values.items() if key not in os.environ
    }
    return build_settings(fallback_values)


def configure_runtime_settings(
    env_path: str | None = None,
    key_path: str | None = None,
) -> Settings:
    """Load and retain runtime settings for an application entry point."""
    global _runtime_settings
    _runtime_settings = load_runtime_settings(env_path=env_path, key_path=key_path)
    return _runtime_settings


def set_runtime_settings(runtime_settings: Settings) -> Settings:
    """Install already-validated settings for a controlled application entry point."""
    global _runtime_settings
    _runtime_settings = runtime_settings
    return _runtime_settings


def get_settings() -> Settings:
    """Return explicit runtime settings, loading encrypted local config once if needed."""
    if _runtime_settings is None:
        return configure_runtime_settings()
    return _runtime_settings


class _SettingsProxy:
    """Compatibility proxy that defers validation until settings are used."""

    def __getattr__(self, name: str):
        return getattr(get_settings(), name)


# Importing config never reads or mutates encrypted configuration. Application
# entry points explicitly call ``configure_runtime_settings`` before routes load.
settings = _SettingsProxy()


def get_database_url(runtime_settings: Settings | None = None) -> URL:

    configured = runtime_settings or settings
    return URL.create(
        drivername="oracle+oracledb",
        username=configured.DB_USER,
        password=configured.DB_PASSWORD,
        host=configured.DB_HOST,
        port=configured.DB_PORT,
        query={"service_name": configured.DB_SERVICE_NAME},
    )
