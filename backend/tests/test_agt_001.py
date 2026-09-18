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

@pytest.fixture(autouse=True)
def isolated_db():
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
    yield TestingSessionLocal
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session(isolated_db):
    db = isolated_db()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client(isolated_db):
    return TestClient(app)

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

def test_agt_001_agent_status_permit_and_deny(client, db_session):
    # 1. Missing X-Agent-Uid header
    resp_missing = client.post("/agent/v1/metrics/bulk", json={
        "batch_uid": str(uuid.uuid4()),
        "sequence": 1,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "items": []
    })
    assert resp_missing.status_code == 422
    assert resp_missing.json()["detail"][0]["msg"] == "Field required"

    # 2. Unknown (NOT_EXIST) agent
    unknown_agent_uid = str(uuid.uuid4())
    resp_unknown = client.post("/agent/v1/metrics/bulk", json={
        "batch_uid": str(uuid.uuid4()),
        "sequence": 1,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "items": []
    }, headers={"X-Agent-Uid": unknown_agent_uid})
    assert resp_unknown.status_code == 401
    assert resp_unknown.json()["detail"] == {
        "success": False,
        "code": "AGENT_NOT_FOUND",
        "message": f"등록되지 않은 에이전트입니다. (uid={unknown_agent_uid})"
    }

    # 3. Deny statuses
    status_messages = {
        "PENDING": "에이전트가 아직 관리자 승인을 받지 않았습니다.",
        "BLOCKED": "에이전트가 차단되었습니다. 관리자에게 문의하세요.",
        "REVOKED": "에이전트 인증이 폐기되었습니다.",
    }
    for status_code, expected_msg in status_messages.items():
        agent = create_agent(db_session, status_code)
        resp_deny = client.post("/agent/v1/metrics/bulk", json={
            "batch_uid": str(uuid.uuid4()),
            "sequence": 1,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "items": []
        }, headers={"X-Agent-Uid": agent.agent_uid})
        assert resp_deny.status_code == 403
        assert resp_deny.json()["detail"] == {
            "success": False,
            "code": "AGENT_NOT_APPROVED",
            "message": expected_msg,
            "current_status": status_code
        }

    # 4. Permit status
    agent_permit = create_agent(db_session, "APPROVED")
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
    resp_permit = client.post("/agent/v1/metrics/bulk", json=payload, headers={"X-Agent-Uid": agent_permit.agent_uid})
    assert resp_permit.status_code == 200
    assert resp_permit.json()["success"] is True
