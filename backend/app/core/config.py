import os
from pydantic_settings import BaseSettings
from cryptography.fernet import Fernet

def load_encrypted_env(env_path: str = ".env.enc", key_path: str = "env.key") -> dict:
    if not os.path.exists(env_path) or not os.path.exists(key_path):
        return {}

    with open(key_path, "rb") as kf:
        key = kf.read()
    
    f = Fernet(key)
    with open(env_path, "rb") as ef:
        encrypted_data = ef.read()
    
    try:
        decrypted_data = f.decrypt(encrypted_data).decode("utf-8")
    except Exception as e:
        print("Failed to decrypt env:", e)
        return {}
        
    env_vars = {}
    for line in decrypted_data.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            env_vars[k.strip()] = v.strip()
    return env_vars

class Settings(BaseSettings):
    DB_USER: str = "example_db_user"
    DB_PASSWORD: str = "CHANGEME"
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 1521
    DB_SERVICE_NAME: str = "ORCL"

    SECRET_KEY: str = os.getenv("SECRET_KEY", "fallback_secret_key_please_change_in_production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 24 hours for convenience

    class Config:
        case_sensitive = True

# 환경변수 로드
encrypted_env = load_encrypted_env()
for key, value in encrypted_env.items():
    os.environ[key] = value

settings = Settings()

def get_database_url() -> str:
    # python-oracledb requires the oracle+oracledb format
    return f"oracle+oracledb://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/?service_name={settings.DB_SERVICE_NAME}"
