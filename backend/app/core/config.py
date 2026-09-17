from __future__ import annotations

import os
from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings, SettingsConfigDict


def load_encrypted_env(env_path: str = ".env.enc", key_path: str = "env.key") -> dict[str, str]:
    """Load local encrypted configuration without logging its values."""
    if not os.path.exists(env_path) or not os.path.exists(key_path):
        return {}
    try:
        key = open(key_path, "rb").read()
        encrypted_data = open(env_path, "rb").read()
        decrypted_data = Fernet(key).decrypt(encrypted_data).decode("utf-8")
    except Exception:
        return {}

    env_vars: dict[str, str] = {}
    for line in decrypted_data.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env_vars[key.strip()] = value.strip()
    return env_vars


# Encrypted local configuration, when present, is loaded before Settings validation.
os.environ.update(load_encrypted_env())


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


def get_database_url() -> str:
    return (
        f"oracle+oracledb://{settings.DB_USER}:{settings.DB_PASSWORD}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/?service_name={settings.DB_SERVICE_NAME}"
    )
