import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def run_preflight(backend_dir=None):
    """
    Check configuration and database connectivity without leaking secrets.
    """
    if backend_dir is None:
        backend_dir = Path(__file__).resolve().parent

    env_enc_path = backend_dir / ".env.enc"
    key_dpapi_path = backend_dir / "env.key.dpapi"

    print(f"Checking configuration at {backend_dir}")

    # 1. Check encrypted artifacts presence
    if not env_enc_path.is_file():
        print(f"[FAIL] Missing {env_enc_path.name}")
        return False
    if not key_dpapi_path.is_file():
        print(f"[FAIL] Missing {key_dpapi_path.name}")
        return False

    print("[OK] Encrypted configuration artifacts found.")

    # 2. Check decryptability
    try:
        from app.core.config import load_encrypted_env
        env_vars = load_encrypted_env(
            env_path=str(env_enc_path),
            key_path=str(key_dpapi_path)
        )
        if not env_vars:
            print("[FAIL] Configuration could not be decrypted or is empty.")
            return False
    except Exception:
        print("[FAIL] Error during configuration decryption (details suppressed).")
        return False

    print("[OK] Configuration successfully decrypted.")

    # 3. Report sanitized endpoint metadata
    db_host = env_vars.get("DB_HOST", "Unknown")
    db_port = env_vars.get("DB_PORT", "Unknown")
    db_service = env_vars.get("DB_SERVICE_NAME", "Unknown")

    print(f"[INFO] Target DB Endpoint: {db_host}:{db_port} (Service: {db_service})")

    # 4. DB connection test (read-only, explicit rollback)
    db_user = env_vars.get("DB_USER")
    db_password = env_vars.get("DB_PASSWORD")

    if not db_user or not db_password:
        print("[FAIL] Database credentials missing from configuration.")
        return False

    from sqlalchemy.engine import URL
    try:
        db_port_number = int(db_port)
    except (TypeError, ValueError):
        print("[FAIL] Database port is invalid.")
        return False

    db_url = URL.create(
        drivername="oracle+oracledb",
        username=db_user,
        password=db_password,
        host=db_host,
        port=db_port_number,
        query={"service_name": db_service},
    )

    try:
        engine = create_engine(db_url, echo=False)
        SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        db = SessionLocal()
        try:
            # Read-only test; explicitly end the transaction even for SELECT.
            db.execute(text("SELECT 1 FROM DUAL"))
            db.rollback()
            print("[OK] Database connection and read test successful.")
        finally:
            db.close()
    except Exception:
        print("[FAIL] Database connection failed (details suppressed).")
        return False

    return True

if __name__ == "__main__":
    success = run_preflight()
    sys.exit(0 if success else 1)
