import getpass
import secrets
from pathlib import Path

from cryptography.fernet import Fernet

from app.core.dpapi import protect_data


def bootstrap():
    print("Initializing environment variables...")
    db_user = input("DB_USER: ").strip()
    db_password = getpass.getpass("DB_PASSWORD: ").strip()
    db_host = input("DB_HOST: ").strip()
    db_port_str = input("DB_PORT: ").strip()
    db_service = input("DB_SERVICE_NAME: ").strip()
    secret_key = getpass.getpass("SECRET_KEY (Press Enter to auto-generate): ").strip()

    if not secret_key:
        secret_key = secrets.token_urlsafe(32)
        print("Generated a new SECRET_KEY.")

    db_port = db_port_str if db_port_str else "1521"

    if not all([db_user, db_password, db_host, db_port, db_service, secret_key]):
        print("Error: All six values are required.")
        return

    env_payload = f"""DB_USER={db_user}
DB_PASSWORD={db_password}
DB_HOST={db_host}
DB_PORT={db_port}
DB_SERVICE_NAME={db_service}
SECRET_KEY={secret_key}
"""

    fernet_key = Fernet.generate_key()
    fernet = Fernet(fernet_key)
    encrypted_env = fernet.encrypt(env_payload.encode("utf-8"))
    dpapi_key = protect_data(fernet_key)

    base_dir = Path(__file__).resolve().parent
    env_enc_path = base_dir / ".env.enc"
    key_dpapi_path = base_dir / "env.key.dpapi"
    env_enc_tmp = env_enc_path.with_suffix(".enc.tmp")
    key_dpapi_tmp = key_dpapi_path.with_suffix(".dpapi.tmp")

    try:
        env_enc_tmp.write_bytes(encrypted_env)
        key_dpapi_tmp.write_bytes(dpapi_key)
        env_enc_tmp.replace(env_enc_path)
        key_dpapi_tmp.replace(key_dpapi_path)
        print("Bootstrap complete. Artifacts written to .env.enc and env.key.dpapi.")
    except Exception:
        if env_enc_tmp.exists():
            env_enc_tmp.unlink()
        if key_dpapi_tmp.exists():
            key_dpapi_tmp.unlink()
        print("Error occurred during bootstrap. Cleaned up temporary files.")


if __name__ == "__main__":
    bootstrap()
