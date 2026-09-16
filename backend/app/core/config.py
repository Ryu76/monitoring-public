import os
from pydantic_settings import BaseSettings
from cryptography.fernet import Fernet
from app.core.dpapi import unprotect_data

def load_encrypted_env(env_path: str = None, key_path: str = None) -> dict:
    if env_path is None or key_path is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        env_path = os.path.join(base_dir, ".env.enc")
        key_path = os.path.join(base_dir, "env.key.dpapi")

    if not os.path.exists(env_path) or not os.path.exists(key_path):
        return {}

    try:
        with open(key_path, "rb") as kf:
            dpapi_key = kf.read()

        fernet_key = unprotect_data(dpapi_key)
        f = Fernet(fernet_key)

        with open(env_path, "rb") as ef:
            encrypted_data = ef.read()

        decrypted_data = f.decrypt(encrypted_data).decode("utf-8")

        env_vars = {}
        for line in decrypted_data.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip()
        return env_vars
    except Exception:
        return {}

class Settings(BaseSettings):
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: int
    DB_SERVICE_NAME: str
    SECRET_KEY: str

    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    class Config:
        case_sensitive = True

encrypted_env = load_encrypted_env()
for key, value in encrypted_env.items():
    if key not in os.environ:
        os.environ[key] = value

settings = Settings()

def get_database_url() -> str:
    return f"oracle+oracledb://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/?service_name={settings.DB_SERVICE_NAME}"
