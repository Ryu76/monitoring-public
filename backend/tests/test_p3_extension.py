import pytest
import os
import sys
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import jwt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["DB_USER"] = "test"
os.environ["DB_PASSWORD"] = "test"
os.environ["DB_HOST"] = "localhost"
os.environ["DB_PORT"] = "1521"
os.environ["DB_SERVICE_NAME"] = "TEST"
os.environ["SECRET_KEY"] = "super-secret-key-for-tests"

from app.main import app
from app.core.database import Base
from app.api.dependencies import get_db
from app.core.config import settings

engine = create_engine("sqlite:///test_p3_extension.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def setup_overrides():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    from app.models.system import SysUser
    with engine.begin() as conn:
        conn.execute(SysUser.__table__.insert().values(user_id=1, login_id="admin_test", user_name="Admin", password_hash="hash", status_code="ACTIVE", use_yn="Y"))
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def auth_headers():
    token = jwt.encode({"sub": "admin_test"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}

def test_external_health_check_create(auth_headers):
    response = client.post(
        "/api/v1/p3/health-checks",
        json={
            "target_type": "URL",
            "target_url_or_path": "https://example.com/api",
            "status": "PASS",
            "mock_response": "200 OK"
        },
        headers=auth_headers
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["target_type"] == "URL"
    assert data["status"] == "PASS"

def test_remote_command_approval_flow(auth_headers):
    response = client.post(
        "/api/v1/p3/remote-commands",
        json={
            "command_type": "ping",
            "target_server": "web-01",
            "requested_by": "test_user"
        },
        headers=auth_headers
    )
    assert response.status_code == 200, response.text
    cmd = response.json()
    assert cmd["approval_state"] == "PENDING"
    assert "dry-run" in cmd["dry_run_result"].lower()

    cmd_id = cmd["id"]
    response = client.put(
        f"/api/v1/p3/remote-commands/{cmd_id}/approve",
        headers=auth_headers
    )
    assert response.status_code == 200, response.text
    approved_cmd = response.json()
    assert approved_cmd["approval_state"] == "APPROVED"
    assert "APPROVED" in approved_cmd["audit_event"]

def test_remote_command_negative(auth_headers):
    response = client.post(
        "/api/v1/p3/remote-commands",
        json={
            "command_type": "rm -rf /",
            "target_server": "web-01",
            "requested_by": "test_user"
        },
        headers=auth_headers
    )
    assert response.status_code == 400
    assert "allowlist" in response.json()["detail"].lower()

def test_config_versioning(auth_headers):
    response = client.post(
        "/api/v1/p3/config-versions",
        json={
            "component_name": "nginx",
            "version_tag": "v1.0.1",
            "config_payload": "worker_processes auto;",
            "rollback_metadata": "previous=v1.0.0"
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["version_tag"] == "v1.0.1"

    response = client.get("/api/v1/p3/config-versions", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) > 0

def test_ha_cluster_state(auth_headers):
    response = client.post(
        "/api/v1/p3/ha-cluster",
        json={
            "node_name": "node-1",
            "role": "LEADER",
            "health_state": "HEALTHY"
        },
        headers=auth_headers
    )
    assert response.status_code == 200

    response = client.get("/api/v1/p3/ha-cluster", headers=auth_headers)
    assert response.status_code == 200
    nodes = response.json()
    assert len(nodes) > 0
    assert nodes[0]["role"] == "LEADER"

def test_external_health_check_negative(auth_headers):
    response = client.post(
        "/api/v1/p3/health-checks",
        json={
            "target_type": "URL",
            "status": "PASS"
        },
        headers=auth_headers
    )
    assert response.status_code == 422

def test_config_versioning_negative(auth_headers):
    response = client.post(
        "/api/v1/p3/config-versions",
        json={
            "component_name": "nginx"
        },
        headers=auth_headers
    )
    assert response.status_code == 422

def test_ha_cluster_state_negative(auth_headers):
    response = client.post(
        "/api/v1/p3/ha-cluster",
        json={
            "node_name": "node-1"
        },
        headers=auth_headers
    )
    assert response.status_code == 422
