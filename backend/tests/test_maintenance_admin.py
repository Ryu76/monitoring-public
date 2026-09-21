import os
import sys
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

os.environ.setdefault("DB_USER", "test-user")
os.environ.setdefault("DB_PASSWORD", "test-password")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "1521")
os.environ.setdefault("DB_SERVICE_NAME", "test-service")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.admin.v1.auth import login_for_access_token
from app.core.database import Base
from app.core.security import verify_password
from app.models.system import SysRole, SysUser, SysUserRole
from reset_maintenance_admin import (
    MAINTENANCE_LOGIN_ID,
    MAINTENANCE_PASSWORD_HASH,
    MAINTENANCE_ROLE_CODE,
    synchronize_maintenance_admin,
)


def make_session() -> tuple[Session, object]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[SysUser.__table__, SysRole.__table__, SysUserRole.__table__],
    )
    return Session(engine), engine


def test_maintenance_account_is_active_privileged_and_can_log_in():
    session, engine = make_session()
    try:
        user = synchronize_maintenance_admin(session)
        session.commit()

        stored_user = session.execute(
            select(SysUser).where(SysUser.login_id == MAINTENANCE_LOGIN_ID)
        ).scalar_one()
        assert stored_user.user_id == user.user_id
        assert stored_user.status_code == "ACTIVE"
        assert stored_user.use_yn == "Y"
        assert verify_password("123456", stored_user.password_hash)

        role = session.execute(
            select(SysRole).where(SysRole.role_code == MAINTENANCE_ROLE_CODE)
        ).scalar_one()
        membership = session.execute(
            select(SysUserRole).where(
                SysUserRole.user_id == stored_user.user_id,
                SysUserRole.role_id == role.role_id,
            )
        ).scalar_one()
        assert membership.user_id == stored_user.user_id

        response = login_for_access_token(
            SimpleNamespace(username="admin", password="123456"), session
        )
        assert response.access_token
        assert response.user_info["login_id"] == "admin"
    finally:
        session.close()
        engine.dispose()


def test_maintenance_synchronization_resets_existing_admin_and_is_idempotent():
    session, engine = make_session()
    try:
        session.add(SysUser(
            user_id=100,
            login_id=MAINTENANCE_LOGIN_ID,
            user_name="Old Admin",
            password_hash="not-a-bcrypt-hash",
            status_code="INACTIVE",
            use_yn="N",
        ))
        session.add(SysRole(
            role_id=200,
            role_code=MAINTENANCE_ROLE_CODE,
            role_name="Disabled Super Administrator",
            use_yn="N",
        ))
        session.commit()

        synchronize_maintenance_admin(session)
        synchronize_maintenance_admin(session)
        session.commit()

        users = session.execute(
            select(SysUser).where(SysUser.login_id == MAINTENANCE_LOGIN_ID)
        ).scalars().all()
        assert len(users) == 1
        assert users[0].user_id == 100
        assert users[0].password_hash == MAINTENANCE_PASSWORD_HASH
        assert verify_password("123456", users[0].password_hash)
        assert users[0].status_code == "ACTIVE"
        assert users[0].use_yn == "Y"

        roles = session.execute(
            select(SysRole).where(SysRole.role_code == MAINTENANCE_ROLE_CODE)
        ).scalars().all()
        assert len(roles) == 1
        assert roles[0].role_id == 200
        assert roles[0].use_yn == "Y"
        memberships = session.execute(select(SysUserRole)).scalars().all()
        assert len(memberships) == 1
    finally:
        session.close()
        engine.dispose()
