from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.dpapi import unprotect_data


def load_encrypted_env(env_path: str | None = None, key_path: str | None = None) -> dict[str, str]:
    """Load DPAPI-protected local development settings without logging values.

    Environment variables supplied by the host remain authoritative.  The encrypted
    files are optional so ordinary test environments can inject settings directly.
    """
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


# The process environment wins over optional DPAPI-protected local development files.
for _key, _value in load_encrypted_env().items():
    os.environ.setdefault(_key, _value)


class Settings(BaseSettings):
    """Required runtime configuration. No database or JWT secret has a source fallback."""

    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: int
    DB_SERVICE_NAME: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    model_config = SettingsConfigDict(case_sensitive=True)


settings = Settings()


from sqlalchemy.engine import URL

def get_database_url() -> URL:
    """Build a structured SQLAlchemy URL so credential delimiters stay data."""
    return URL.create(
        drivername="oracle+oracledb",
        username=settings.DB_USER,
        password=settings.DB_PASSWORD,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        query={"service_name": settings.DB_SERVICE_NAME},
    )
