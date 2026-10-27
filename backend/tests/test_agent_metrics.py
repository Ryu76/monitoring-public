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
from app.models.resource import MetricCurrent, MetricReceiptLedger
from app.api.dependencies import get_db
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

client = TestClient(app)

@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def test_agent(db_session: Session):
    # Create server and agent for testing
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
    db_session.refresh(agent)
    
    return agent

def test_ing_001_batch_idempotency(db_session, test_agent):
    batch_uid = str(uuid.uuid4())
    payload = {
        "batch_uid": batch_uid,
        "sequence": 1,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "items": [
            {
                "metric_code": "CPU_USAGE_PCT",
                "dimension_key": "core",
                "dimension_value": "all",
                "metric_value": 50.0,
                "collected_at": datetime.now(timezone.utc).isoformat()
            }
        ]
    }
    headers = {"X-Agent-Uid": test_agent.agent_uid}
    
    # 1st attempt
    resp1 = client.post("/agent/v1/metrics/bulk", json=payload, headers=headers)
    assert resp1.status_code == 200
    assert resp1.json()["received_count"] == 1
    
    # 2nd attempt with same batch_uid
    resp2 = client.post("/agent/v1/metrics/bulk", json=payload, headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["message"] == f"배치({batch_uid})가 이미 처리되었습니다."
    
    # Check ledger
    ledger = db_session.query(MetricReceiptLedger).filter(MetricReceiptLedger.batch_uid == batch_uid).first()
    assert ledger is not None
    assert ledger.item_count == 1

def test_ing_002_monotonic_upsert(db_session, test_agent):
    batch_uid_1 = str(uuid.uuid4())
    batch_uid_2 = str(uuid.uuid4())
    headers = {"X-Agent-Uid": test_agent.agent_uid}
    
    now = datetime.now(timezone.utc)
    past = now - timedelta(minutes=5)
    
    # Send NEW metric first
    payload_new = {
        "batch_uid": batch_uid_1,
        "sequence": 1,
        "collected_at": now.isoformat(),
        "items": [
            {
                "metric_code": "MEM_USAGE_PCT",
                "dimension_key": "-",
                "dimension_value": "-",
                "metric_value": 80.0,
                "collected_at": now.isoformat()
            }
        ]
    }
    client.post("/agent/v1/metrics/bulk", json=payload_new, headers=headers)
    
    # Send OLD metric later
    payload_old = {
        "batch_uid": batch_uid_2,
        "sequence": 2,
        "collected_at": past.isoformat(),
        "items": [
            {
                "metric_code": "MEM_USAGE_PCT",
                "dimension_key": "-",
                "dimension_value": "-",
                "metric_value": 20.0,
                "collected_at": past.isoformat()
            }
        ]
    }
    client.post("/agent/v1/metrics/bulk", json=payload_old, headers=headers)
    
    # Check current metric is still 80.0
    curr = db_session.query(MetricCurrent).filter(
        MetricCurrent.server_id == test_agent.server_id,
        MetricCurrent.metric_code == "MEM_USAGE_PCT"
    ).first()
    assert curr is not None
    assert curr.metric_value == 80.0

def test_ing_003_metric_def_update(db_session, test_agent):
    """Test that existing incorrect rate metric definitions are safely updated to float/bytes_per_sec/avg."""
    from app.models.resource import MetricDef
    
    # Pre-insert a 'legacy' incorrect definition for NET_BYTES_SENT_RATE (BIGINT, BYTES, SUM)
    legacy_def = MetricDef(
        metric_code="NET_BYTES_SENT_RATE",
        metric_name="Network Bytes Sent Rate",
        category_code="NETWORK",
        value_type_code="BIGINT",
        unit_code="BYTES",
        agg_type_code="SUM",
        windows_support_yn="Y",
        linux_support_yn="Y",
        use_yn="Y",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(legacy_def)
    db_session.commit()
    
    batch_uid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    payload = {
        "batch_uid": batch_uid,
        "sequence": 1,
        "collected_at": now.isoformat(),
        "items": [
            {
                "metric_code": "NET_BYTES_SENT_RATE",
                "dimension_key": "interface",
                "dimension_value": "eth0",
                "metric_value": 105.5,
                "collected_at": now.isoformat()
            },
            {
                "metric_code": "NET_BYTES_RECV_RATE",
                "dimension_key": "interface",
                "dimension_value": "eth0",
                "metric_value": 205.5,
                "collected_at": now.isoformat()
            }
        ]
    }
    
    headers = {"X-Agent-Uid": test_agent.agent_uid}
    resp = client.post("/agent/v1/metrics/bulk", json=payload, headers=headers)
    assert resp.status_code == 200
    
    # Verify that the pre-existing NET_BYTES_SENT_RATE definition was updated
    updated_def = db_session.get(MetricDef, "NET_BYTES_SENT_RATE")
    assert updated_def.value_type_code == "FLOAT"
    assert updated_def.unit_code == "BYTES_PER_SEC"
    assert updated_def.agg_type_code == "AVG"
    
    # Verify that the non-existing NET_BYTES_RECV_RATE definition was created correctly
    new_def = db_session.get(MetricDef, "NET_BYTES_RECV_RATE")
    assert new_def is not None
    assert new_def.value_type_code == "FLOAT"
    assert new_def.unit_code == "BYTES_PER_SEC"
    assert new_def.agg_type_code == "AVG"

@pytest.fixture(autouse=True)
def setup_overrides():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
