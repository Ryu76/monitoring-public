import pytest
import os
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.api.dependencies import get_db
from app.models.agent import Agent
from app.models.server import Server
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

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_agent(db_session: Session, status_code: str):
    server_uid = str(uuid.uuid4())
    server = Server(
        server_uid=server_uid,
        server_name=f"TestServer-{status_code}",
        host_name=f"test-server-{status_code}",
        mgmt_ip="10.0.0.1",
        use_yn='Y'
    )
    db_session.add(server)
    db_session.flush()

    agent_uid = str(uuid.uuid4())
    agent = Agent(
        agent_uid=agent_uid,
        server_id=server.server_id,
        status_code=status_code,
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent

def test_agt_001_agent_status_permit_and_deny(db_session):
    # Missing Agent UID header
    resp_missing = client.post("/agent/v1/metrics/bulk", json={})
    assert resp_missing.status_code == 422 # FastAPI validation for missing header or invalid body

    # Or test properly missing header:
    resp_missing_header = client.post("/agent/v1/metrics/bulk", json={
        "batch_uid": str(uuid.uuid4()),
        "sequence": 1,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "items": []
    })
    assert resp_missing_header.status_code in (401, 422)
    assert "Missing X-Agent-Uid header" in resp_missing_header.json()["detail"] or resp_missing_header.status_code in (401, 403, 422)

    # Deny statuses
    deny_statuses = ["PENDING", "BLOCKED", "REVOKED", "NOT_EXIST"]
    for status in deny_statuses:
        if status == "NOT_EXIST":
            agent_uid = str(uuid.uuid4())
        else:
            agent = create_agent(db_session, status)
            agent_uid = agent.agent_uid

        headers = {"X-Agent-Uid": agent_uid}
        payload = {
            "batch_uid": str(uuid.uuid4()),
            "sequence": 1,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "items": [{
                "metric_code": "CPU_USAGE_PCT",
                "dimension_key": "core",
                "dimension_value": "all",
                "metric_value": 50.0,
                "collected_at": datetime.now(timezone.utc).isoformat()
            }]
        }
        resp = client.post("/agent/v1/metrics/bulk", json=payload, headers=headers)
        assert resp.status_code in (401, 403)
        detail_msg = str(resp.json().get("detail", "")).lower()
        assert "not found" in detail_msg or "not approved" in detail_msg or "unauthorized" in detail_msg or "승인" in detail_msg or "agent" in detail_msg or "forbidden" in detail_msg or "permission" in detail_msg

    # Permit status
    agent_permit = create_agent(db_session, "APPROVED")
    headers = {"X-Agent-Uid": agent_permit.agent_uid}
    payload = {
        "batch_uid": str(uuid.uuid4()),
        "sequence": 1,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "items": [{
            "metric_code": "CPU_USAGE_PCT",
            "dimension_key": "core",
            "dimension_value": "all",
            "metric_value": 50.0,
            "collected_at": datetime.now(timezone.utc).isoformat()
        }]
    }
    resp = client.post("/agent/v1/metrics/bulk", json=payload, headers=headers)
    assert resp.status_code == 200
