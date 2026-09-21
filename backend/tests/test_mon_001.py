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
import uuid

from app.main import app
from app.models.agent import Agent
from app.models.server import Server
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

client = TestClient(app)

@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def test_server_agent(db_session: Session):
    from app.models.system import SysRole, SysUserRole
    # Add auth data
    user = SysUser(user_id=1, login_id="admin", user_name="Admin", use_yn="Y", status_code="ACTIVE", password_hash="test")
    role = SysRole(role_id=1, role_code="ADMIN", role_name="Admin")
    user_role = SysUserRole(user_id=1, role_id=1)
    db_session.merge(user)
    db_session.merge(role)
    db_session.merge(user_role)

    server_uid = str(uuid.uuid4())
    server = Server(
        server_uid=server_uid,
        server_name="TestServer_MON001",
        host_name="mon001-server",
        mgmt_ip="10.0.0.10",
        use_yn='Y'
    )
    db_session.add(server)
    db_session.flush()

    agent_uid = str(uuid.uuid4())
    agent = Agent(
        agent_uid=agent_uid,
        server_id=server.server_id,
        status_code="APPROVED",
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(server)
    db_session.refresh(agent)
    return server, agent

def test_mon_001_check_targets_crud(db_session, test_server_agent):
    server, agent = test_server_agent

    # 1. Add check targets
    payload = {
        "processes": ["nginx", "python"],
        "services": ["sshd"],
        "ports": [80, 443]
    }
    resp = client.put(f"/api/v1/servers/{server.server_id}/check-targets", json=payload)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "nginx" in data["processes"]
    assert "python" in data["processes"]
    assert "sshd" in data["services"]
    assert 80 in data["ports"]
    assert 443 in data["ports"]

    # 2. Agent receives config
    resp = client.get("/agent/v1/config", headers={"X-Agent-Uid": agent.agent_uid})
    assert resp.status_code == 200
    config_data = resp.json()["data"]
    assert "nginx" in config_data["check_processes"]
    assert "sshd" in config_data["check_services"]
    assert 80 in config_data["check_ports"]

def test_mon_001_check_history_and_current(db_session, test_server_agent):
    server, agent = test_server_agent

    # Simulate Agent sending check results
    batch_uid = str(uuid.uuid4())
    payload = {
        "batch_uid": batch_uid,
        "sequence": 1,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "items": [
            {
                "metric_code": "PROCESS_STATUS",
                "dimension_key": "process_name",
                "dimension_value": "nginx",
                "metric_value": 1.0,
                "status_code": "NORMAL",
                "collected_at": datetime.now(timezone.utc).isoformat()
            },
            {
                "metric_code": "PORT_LISTEN",
                "dimension_key": "port",
                "dimension_value": "80",
                "metric_value": 0.0,
                "status_code": "CRITICAL",
                "collected_at": datetime.now(timezone.utc).isoformat()
            }
        ]
    }

    resp = client.post("/agent/v1/metrics/bulk", json=payload, headers={"X-Agent-Uid": agent.agent_uid})
    assert resp.status_code == 200

    # Verify Current Status
    resp = client.get(f"/api/v1/servers/{server.server_id}")
    assert resp.status_code == 200
    metrics = resp.json()["data"]["metrics"]

    nginx_metric = next((m for m in metrics if m["dimension_value"] == "nginx"), None)
    assert nginx_metric is not None
    assert nginx_metric["metric_value"] == 1.0

    port_metric = next((m for m in metrics if m["dimension_value"] == "80"), None)
    assert port_metric is not None
    assert port_metric["metric_value"] == 0.0

    # Verify History
    resp = client.get(f"/api/v1/servers/{server.server_id}/check-history")
    assert resp.status_code == 200
    history = resp.json()["data"]

    assert len(history) == 2
    types = [h["target_type_code"] for h in history]
    assert "PROCESS" in types
    assert "PORT" in types

@pytest.fixture(autouse=True)
def setup_overrides():
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    yield
    app.dependency_overrides.clear()
