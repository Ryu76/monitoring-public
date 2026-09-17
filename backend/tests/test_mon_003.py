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
from datetime import datetime, timezone, timedelta
import uuid

from app.main import app
from app.models.agent import Agent
from app.models.server import Server
from app.models.resource import MetricCurrent, MetricHistory
from app.api.dependencies import get_db, get_current_user
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base

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
    from app.models.system import SysUser
    return SysUser(user_id=1, login_id="admin_test", user_name="Admin")

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

def test_mon_003_history(db_session: Session):
    server_uid = str(uuid.uuid4())
    server = Server(
        server_uid=server_uid,
        server_name="TestServer",
        host_name="test-server",
        mgmt_ip="10.0.0.1",
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
    
    # Send metrics
    now = datetime.now(timezone.utc)
    payload = {
        "batch_uid": str(uuid.uuid4()),
        "sequence": 1,
        "collected_at": now.isoformat(),
        "items": [
            {
                "metric_code": "CPU_USAGE_PCT",
                "dimension_key": "-",
                "dimension_value": "-",
                "metric_value": 45.0,
                "collected_at": (now - timedelta(minutes=10)).isoformat()
            },
            {
                "metric_code": "CPU_USAGE_PCT",
                "dimension_key": "-",
                "dimension_value": "-",
                "metric_value": 55.0,
                "collected_at": now.isoformat()
            }
        ]
    }
    resp = client.post("/agent/v1/metrics/bulk", json=payload, headers={"X-Agent-Uid": agent.agent_uid})
    assert resp.status_code == 200
    
    # Query history
    resp_hist = client.get(f"/api/v1/servers/{server.server_id}/metrics/CPU_USAGE_PCT/history")
    assert resp_hist.status_code == 200
    data = resp_hist.json()["data"]
    assert len(data) == 2
    assert data[0]["metric_value"] == 45.0
    assert data[1]["metric_value"] == 55.0
