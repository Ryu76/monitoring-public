from __future__ import annotations

from sqlalchemy.engine import URL

from app.core.config import Settings
from app.core.security import create_access_token, get_password_hash
from app.models.system import SysRole, SysUser, SysUserRole


def _token(login_id: str) -> dict[str, str]:
    token = create_access_token({"sub": login_id})
    return {"Authorization": f"Bearer {token}"}


def _add_user(session, user_id: int, login_id: str, *, password: str = "correct-password", active: bool = True):
    user = SysUser(
        user_id=user_id,
        login_id=login_id,
        user_name=login_id,
        password_hash=get_password_hash(password),
        status_code="ACTIVE" if active else "INACTIVE",
        use_yn="Y",
    )
    session.add(user)
    return user


def _add_role(session, role_id: int, code: str, *, enabled: bool = True):
    role = SysRole(
        role_id=role_id,
        role_code=code,
        role_name=code,
        use_yn="Y" if enabled else "N",
    )
    session.add(role)
    return role


def _assign_role(session, user_id: int, role_id: int):
    session.add(SysUserRole(user_id=user_id, role_id=role_id))


def test_login_uses_database_password_and_has_no_maintenance_bypass(api_client, db_session):
    _add_user(db_session, 1, "db-admin", password="database-only-password")
    db_session.commit()

    successful = api_client.post(
        "/api/v1/admin/auth/login",
        data={"username": "db-admin", "password": "database-only-password"},
    )
    assert successful.status_code == 200
    assert successful.json()["user_info"]["login_id"] == "db-admin"

    # The maintenance credentials must not authenticate unless a matching DB row
    # was explicitly provisioned with the corresponding bcrypt hash.
    rejected = api_client.post(
        "/api/v1/admin/auth/login",
        data={"username": "admin", "password": "123456"},
    )
    assert rejected.status_code == 401


def test_inactive_database_account_is_forbidden(api_client, db_session):
    _add_user(db_session, 1, "inactive", password="correct-password", active=False)
    db_session.commit()

    response = api_client.post(
        "/api/v1/admin/auth/login",
        data={"username": "inactive", "password": "correct-password"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Inactive user account"


def test_all_admin_user_endpoints_reject_non_super_admin(api_client, db_session):
    _add_user(db_session, 1, "operator")
    _add_user(db_session, 2, "target")
    _add_role(db_session, 1, "ADMIN")
    _assign_role(db_session, 1, 1)
    db_session.commit()
    headers = _token("operator")

    requests = (
        ("get", "/api/v1/admin/users/", {}),
        ("get", "/api/v1/admin/users/2", {}),
        (
            "post",
            "/api/v1/admin/users/",
            {"json": {"login_id": "new-user", "user_name": "New", "password": "password"}},
        ),
        ("put", "/api/v1/admin/users/2", {"json": {"user_name": "Changed"}}),
        ("delete", "/api/v1/admin/users/2", {}),
    )
    for method, path, kwargs in requests:
        response = getattr(api_client, method)(path, headers=headers, **kwargs)
        assert response.status_code == 403, f"{method.upper()} {path}: {response.text}"


def test_disabled_super_admin_role_is_not_authorized(api_client, db_session):
    _add_user(db_session, 1, "disabled-super")
    _add_role(db_session, 1, "SUPER_ADMIN", enabled=False)
    _assign_role(db_session, 1, 1)
    db_session.commit()

    response = api_client.get("/api/v1/admin/users/", headers=_token("disabled-super"))
    assert response.status_code == 403


def test_last_active_super_admin_cannot_be_disabled(api_client, db_session):
    _add_user(db_session, 1, "only-super")
    _add_role(db_session, 1, "SUPER_ADMIN")
    _assign_role(db_session, 1, 1)
    db_session.commit()

    response = api_client.put(
        "/api/v1/admin/users/1",
        headers=_token("only-super"),
        json={"use_yn": "N"},
    )
    assert response.status_code == 400
    assert "last active SUPER_ADMIN" in response.json()["detail"]


def test_db_schema_is_validated_and_oracle_engine_maps_schema_without_affecting_sqlite():
    settings = Settings(
        DB_USER="user",
        DB_PASSWORD="password",
        DB_HOST="host",
        DB_PORT=1521,
        DB_SERVICE_NAME="service",
        SECRET_KEY="secret",
        DB_SCHEMA="APP_OWNER",
    )
    assert settings.DB_SCHEMA == "APP_OWNER"

    from pydantic_core import ValidationError

    try:
        Settings(
            DB_USER="user",
            DB_PASSWORD="password",
            DB_HOST="host",
            DB_PORT=1521,
            DB_SERVICE_NAME="service",
            SECRET_KEY="secret",
            DB_SCHEMA="APP-OWNER",
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("invalid Oracle schema identifier was accepted")

    from app.core.database import create_database_engine

    sqlite_engine = create_database_engine("sqlite://", db_schema="APP_OWNER")
    assert sqlite_engine.get_execution_options().get("schema_translate_map") is None
    sqlite_engine.dispose()

    oracle_url = URL.create(
        "oracle+oracledb",
        username="user",
        password="password",
        host="host",
        port=1521,
        query={"service_name": "service"},
    )
    oracle_engine = create_database_engine(oracle_url, db_schema="APP_OWNER")
    assert oracle_engine.get_execution_options()["schema_translate_map"] == {None: "APP_OWNER"}
    oracle_engine.dispose()
