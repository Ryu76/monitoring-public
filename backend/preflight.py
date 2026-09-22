from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import sessionmaker

from app.core.config import (
    build_settings,
    get_database_url,
    load_encrypted_env,
    set_runtime_settings,
)

CORE_TABLES = ("SYS_USER", "SYS_ROLE", "SYS_USER_ROLE")


def _required_table_statement() -> tuple[object, dict[str, str]]:
    table_bindings = {f"table_{index}": table for index, table in enumerate(CORE_TABLES)}
    placeholders = ", ".join(f":{key}" for key in table_bindings)
    statement = text(
        "SELECT table_name FROM all_tables "
        "WHERE owner = :owner AND table_name IN (" + placeholders + ")"
    )
    return statement, table_bindings


def run_preflight(backend_dir: Path | None = None) -> bool:
    """Validate encrypted configuration and read-only Oracle access without leaks."""
    backend_dir = backend_dir or Path(__file__).resolve().parent
    env_enc_path = backend_dir / ".env.enc"
    key_dpapi_path = backend_dir / "env.key.dpapi"

    print("Checking encrypted configuration artifacts.")
    if not env_enc_path.is_file():
        print("[FAIL] Missing .env.enc")
        return False
    if not key_dpapi_path.is_file():
        print("[FAIL] Missing env.key.dpapi")
        return False
    print("[OK] Encrypted configuration artifacts found.")

    try:
        encrypted_values = load_encrypted_env(
            env_path=str(env_enc_path),
            key_path=str(key_dpapi_path),
        )
        if not encrypted_values:
            print("[FAIL] Configuration could not be decrypted or is empty.")
            return False
        configured = build_settings(encrypted_values)
        set_runtime_settings(configured)
    except Exception:
        print("[FAIL] Configuration validation failed (details suppressed).")
        return False
    print("[OK] Configuration artifacts decrypted and validated.")

    try:
        from app.core.database import create_database_engine
        from app.models.system import SysUser

        engine = create_database_engine(
            get_database_url(configured),
            db_schema=configured.DB_SCHEMA,
        )
        session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        db = session_factory()
        try:
            db.execute(text("SELECT 1 FROM DUAL"))

            table_statement, table_bindings = _required_table_statement()
            rows = db.execute(
                table_statement,
                {"owner": configured.DB_SCHEMA.upper(), **table_bindings},
            ).scalars().all()
            available_tables = {str(row).upper() for row in rows}
            missing_tables = set(CORE_TABLES) - available_tables
            if missing_tables:
                print("[FAIL] Required core table availability check failed.")
                return False

            # The engine's Oracle schema_translate_map applies the configured
            # schema to this intentionally schema-less ORM model.
            db.execute(select(SysUser).limit(1))
        finally:
            # SELECT can still start a transaction on Oracle; never leave it open.
            db.rollback()
            db.close()
    except Exception:
        print("[FAIL] Database read-only preflight failed (details suppressed).")
        return False

    print("[OK] Database read-only preflight completed.")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if run_preflight() else 1)
