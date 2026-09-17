import pytest
import os
os.environ["DB_USER"] = "test"
os.environ["DB_PASSWORD"] = "test"
os.environ["DB_HOST"] = "localhost"
os.environ["DB_PORT"] = "1521"
os.environ["DB_SERVICE_NAME"] = "TEST"
os.environ["SECRET_KEY"] = "test"

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.main import app
from app.models.event import Incident, Event
from app.api.dependencies import get_db, get_current_user
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base
from app.models.system import SysUser

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

def override_get_current_user():
    return SysUser(
        user_id=1,
        login_id="admin",
        user_name="Admin",
        use_yn="Y"
    )

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user
client = TestClient(app)

@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def test_data(db_session: Session):
    from app.models.system import SysRole, SysUserRole
    user = SysUser(user_id=1, login_id="admin", user_name="Admin", use_yn="Y", status_code="ACTIVE", password_hash="test")
    role = SysRole(role_id=1, role_code="ADMIN", role_name="Admin")
    user_role = SysUserRole(user_id=1, role_id=1)
    db_session.merge(user)
    db_session.merge(role)
    db_session.merge(user_role)
    db_session.commit()

    inc = Incident(
        incident_id=1,
        incident_title="Test Incident",
        status_code="OPEN",
        impact_code="HIGH",
        cause_code="UNKNOWN",
        detected_at=datetime.now(timezone.utc),
        created_by="TEST"
    )
    db_session.add(inc)
    db_session.commit()
    return inc

def test_inc_001_incident_transitions(db_session, test_data):
    incident_id = test_data.incident_id

    # 1. Close the incident
    payload = {
        "status_code": "CLOSED"
    }
    resp = client.put(f"/api/v1/incidents/{incident_id}", json=payload)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status_code"] == "CLOSED"
    assert data["closed_at"] is not None

    # 2. Reopen the incident via action
    payload_action = {
        "action_note": "Reopened for further investigation",
        "status_code": "OPEN"
    }
    resp = client.post(f"/api/v1/incidents/{incident_id}/actions", json=payload_action)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status_code"] == "OPEN"
    assert data["closed_at"] is None
    assert data["resolved_at"] is None
    assert len(data["actions"]) == 1
