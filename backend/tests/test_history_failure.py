import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DB_USER"] = "test"
os.environ["DB_PASSWORD"] = "test"
os.environ["DB_HOST"] = "localhost"
os.environ["DB_PORT"] = "1521"
os.environ["DB_SERVICE_NAME"] = "TEST"
os.environ["SECRET_KEY"] = "super-secret-key-for-tests"

# Removed global patch

from app.main import app
from app.api.dependencies import get_db
from app.core.database import Base
from app.models.agent import Agent
from app.models.server import Server
from app.models.resource import (
    CheckSnapshotWatermark,
    MetricHistory,
    MetricCurrent,
    MetricReceiptLedger,
)
import datetime

from sqlalchemy.pool import StaticPool
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
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

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(Server.__table__.insert().values(server_id=1, server_uid="123", server_name="test-server", host_name="test-server", mgmt_ip="10.0.0.1", use_yn="Y"))
        conn.execute(Agent.__table__.insert().values(agent_id=1, agent_uid="123", server_id=1, agent_version="1.0", status_code="APPROVED"))
    yield
    Base.metadata.drop_all(bind=engine)

def test_history_failure_rolls_back_everything():
    """If history insertion fails, the transaction must roll back."""
    # We will simulate history failure by dropping the history table temporarily!

    with engine.begin() as conn:
        MetricHistory.__table__.drop(engine)

    payload = {
        "batch_uid": "batch-fail-test-123",
        "sequence": 1,
        "collected_at": datetime.datetime.now().isoformat(),
        "items": [
            {
                "metric_code": "cpu_usage",
                "metric_value": 45.0,
                "collected_at": datetime.datetime.now().isoformat()
            }
        ]
    }

    response = client.post("/agent/v1/metrics/bulk", json=payload, headers={"X-Agent-Uid": "123"})
    # The API should return 500 because the transaction failed
    assert response.status_code == 500, response.text

    # Ensure ledger is NOT saved
    with engine.connect() as conn:
        ledger = conn.execute(MetricReceiptLedger.__table__.select()).fetchall()
        assert len(ledger) == 0

        curr = conn.execute(MetricCurrent.__table__.select()).fetchall()
        assert len(curr) == 0

def test_stale_snapshot_watermark():
    """An older item snapshot cannot delete current rows or advance its watermark."""

    # Send batch 1 with newer timestamp
    payload_new = {
        "batch_uid": "batch-new-1",
        "sequence": 1,
        # The envelope time is transport metadata; item times drive snapshots.
        "collected_at": "2026-09-18T08:00:00",
        "items": [
            {
                "metric_code": "PROCESS_STATUS",
                "metric_value": 10,
                "dimension_value": "python",
                "collected_at": "2026-09-18T10:00:00"
            },
            {
                "metric_code": "PROCESS_STATUS",
                "metric_value": 20,
                "dimension_value": "nginx",
                "collected_at": "2026-09-18T10:00:00"
            }
        ]
    }
    resp1 = client.post("/agent/v1/metrics/bulk", json=payload_new, headers={"X-Agent-Uid": "123"})
    assert resp1.status_code == 200, resp1.text

    # Send batch 2 with older timestamp (stale snapshot)
    payload_old = {
        "batch_uid": "batch-old-1",
        "sequence": 1,
        # A later envelope must not make its older item snapshot acceptable.
        "collected_at": "2026-09-18T12:00:00",
        "items": [
            {
                "metric_code": "PROCESS_STATUS",
                "metric_value": 5,
                "dimension_value": "python",
                "collected_at": "2026-09-18T09:00:00"
            }
        ]
    }
    resp2 = client.post("/agent/v1/metrics/bulk", json=payload_old, headers={"X-Agent-Uid": "123"})
    assert resp2.status_code == 200, resp2.text

    # No current row is deleted/replaced and the accepted item timestamp is
    # retained as the watermark, rather than either envelope timestamp.
    with engine.connect() as conn:
        curr = conn.execute(
            MetricCurrent.__table__.select().where(
                MetricCurrent.metric_code == "PROCESS_STATUS"
            )
        ).fetchall()
        assert {(row.dimension_value, row.metric_value) for row in curr} == {
            ("python", 10),
            ("nginx", 20),
        }
        watermark = conn.execute(CheckSnapshotWatermark.__table__.select()).one()
        assert watermark.collected_at.isoformat() == "2026-09-18T10:00:00"


def test_same_batch_current_upsert_preserves_history_and_latest_item_timestamp():
    """A repeated current PK in one batch has one latest current row and two histories."""
    payload = {
        "batch_uid": "batch-current-upsert-1",
        "sequence": 1,
        # The current timestamp must come from the individual observations.
        "collected_at": "2026-09-18T08:00:00",
        "items": [
            {
                "metric_code": "CPU_USAGE_PCT",
                "metric_value": 25,
                "dimension_key": "cpu",
                "dimension_value": "total",
                "collected_at": "2026-09-18T10:00:00",
            },
            {
                "metric_code": "CPU_USAGE_PCT",
                "metric_value": 50,
                "dimension_key": "cpu",
                "dimension_value": "total",
                "collected_at": "2026-09-18T11:00:00",
            },
        ],
    }

    response = client.post("/agent/v1/metrics/bulk", json=payload, headers={"X-Agent-Uid": "123"})
    assert response.status_code == 200, response.text
    assert response.json()["received_count"] == 2

    with engine.connect() as conn:
        current = conn.execute(
            MetricCurrent.__table__.select().where(
                MetricCurrent.metric_code == "CPU_USAGE_PCT"
            )
        ).one()
        assert current.metric_value == 50
        assert current.collected_at.isoformat() == "2026-09-18T11:00:00"

        history = conn.execute(
            MetricHistory.__table__.select().where(
                MetricHistory.metric_code == "CPU_USAGE_PCT"
            ).order_by(MetricHistory.collected_at)
        ).fetchall()
        assert [(row.metric_value, row.collected_at.isoformat()) for row in history] == [
            (25, "2026-09-18T10:00:00"),
            (50, "2026-09-18T11:00:00"),
        ]
