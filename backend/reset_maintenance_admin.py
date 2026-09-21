from __future__ import annotations

import argparse
from datetime import datetime, timezone

from typing import TYPE_CHECKING

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.models.system import SysUser


MAINTENANCE_LOGIN_ID = "admin"
MAINTENANCE_PASSWORD_HASH = "$2b$12$VjSlKCW5wk3U7eKwTxEpr.W20jjHmdVEYXYwMXdBxhvIeC3gdB/ca"
MAINTENANCE_ROLE_CODE = "SUPER_ADMIN"


def synchronize_maintenance_admin(db: Session) -> SysUser:
    from app.models.system import SysRole, SysUser, SysUserRole

    now = datetime.now(timezone.utc)
    user = db.execute(
        select(SysUser).where(SysUser.login_id == MAINTENANCE_LOGIN_ID)
    ).scalar_one_or_none()
    if user is None:
        user = SysUser(
            login_id=MAINTENANCE_LOGIN_ID,
            user_name="Maintenance Administrator",
            password_hash=MAINTENANCE_PASSWORD_HASH,
            status_code="ACTIVE",
            use_yn="Y",
            created_at=now,
            created_by="maintenance-bootstrap",
        )
        db.add(user)
    else:
        user.password_hash = MAINTENANCE_PASSWORD_HASH
        user.status_code = "ACTIVE"
        user.use_yn = "Y"
        user.updated_at = now
        user.updated_by = "maintenance-bootstrap"
    db.flush()

    role = db.execute(
        select(SysRole).where(SysRole.role_code == MAINTENANCE_ROLE_CODE)
    ).scalar_one_or_none()
    if role is None:
        role = SysRole(
            role_code=MAINTENANCE_ROLE_CODE,
            role_name="Super Administrator",
            use_yn="Y",
            created_at=now,
            created_by="maintenance-bootstrap",
        )
        db.add(role)
        db.flush()
    else:
        role.use_yn = "Y"

    membership = db.execute(
        select(SysUserRole).where(
            SysUserRole.user_id == user.user_id,
            SysUserRole.role_id == role.role_id,
        )
    ).scalar_one_or_none()
    if membership is None:
        db.add(SysUserRole(
            user_id=user.user_id,
            role_id=role.role_id,
            created_at=now,
            created_by="maintenance-bootstrap",
        ))
    return user


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create or reset the maintenance administrator account."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the maintenance account change to the configured database.",
    )
    args = parser.parse_args()
    if not args.apply:
        parser.error("--apply is required because this command changes the configured database.")

    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        user = synchronize_maintenance_admin(db)
        db.commit()
        print(f"Maintenance account synchronized: {user.login_id}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
