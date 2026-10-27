from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app import scheduler, worker
from app.api.web.v1.router import get_incidents
from app.core.database import Base
from app.core.query_batches import ORACLE_IN_LIST_CHUNK_SIZE, oracle_in_chunks
from app.models.agent import Agent, AgentStatusCurr
from app.models.event import Event, EventRule, Incident, IncidentAction
from app.models.resource import MetricCurrent


def count_selects(engine):
    count = 0

    def listener(_conn, _cursor, statement, *_args):
        nonlocal count
        if statement.lstrip().upper().startswith("SELECT"):
            count += 1

    event.listen(engine, "before_cursor_execute", listener)
    return lambda: count, listener


def test_incident_list_uses_one_query_and_selects_deterministic_latest_action():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Incident.__table__, IncidentAction.__table__])
    session = Session(engine)
    now = datetime.now(timezone.utc)
    session.add_all([
        Incident(incident_id=1, incident_title="first", status_code="OPEN"),
        Incident(incident_id=2, incident_title="second", status_code="OPEN"),
        IncidentAction(action_id=1, incident_id=1, action_note="old", action_at=now),
        IncidentAction(action_id=2, incident_id=1, action_note="new", action_at=now),
    ])
    session.commit()
    get_count, listener = count_selects(engine)
    try:
        result = get_incidents(session)
        assert get_count() == 1
        by_id = {item["incident_id"]: item for item in result["data"]}
        assert by_id[1]["latest_action_note"] == "new"
        assert by_id[2]["latest_action_note"] is None
    finally:
        event.remove(engine, "before_cursor_execute", listener)
        session.close()
        engine.dispose()


def test_threshold_worker_preloads_open_events_once(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[EventRule.__table__, MetricCurrent.__table__, Event.__table__])
    session = Session(engine)
    now = datetime.now(timezone.utc)
    session.add_all([
        EventRule(
            rule_id=1,
            rule_name="cpu",
            target_metric="CPU_USAGE_PCT",
            compare_op=">=",
            warn_threshold=50,
            crit_threshold=80,
            fatal_threshold=95,
            use_yn="Y",
        ),
        MetricCurrent(
            server_id=1,
            metric_code="CPU_USAGE_PCT",
            dimension_key="-",
            dimension_value="all",
            metric_value=90,
            collected_at=now,
            received_at=now,
        ),
        MetricCurrent(
            server_id=2,
            metric_code="CPU_USAGE_PCT",
            dimension_key="-",
            dimension_value="all",
            metric_value=99,
            collected_at=now,
            received_at=now,
        ),
        Event(
            event_uid="open-1",
            rule_id=1,
            server_id=1,
            target_key="all",
            severity_code="WARNING",
            status_code="OPEN",
            title="old",
            first_occurred_at=now,
        ),
    ])
    session.commit()
    monkeypatch.setattr(worker, "SessionLocal", lambda: session)
    get_count, listener = count_selects(engine)
    try:
        worker.check_thresholds()
        assert get_count() == 3
        with Session(engine) as verify:
            events = verify.execute(select(Event).where(Event.status_code == "OPEN")).scalars().all()
            assert len(events) == 2
            assert next(item for item in events if item.server_id == 1).severity_code == "CRITICAL"
    finally:
        event.remove(engine, "before_cursor_execute", listener)
        engine.dispose()


def test_offline_scheduler_batch_loads_agent_and_event_state(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Agent.__table__, AgentStatusCurr.__table__, Event.__table__])
    session = Session(engine)
    now = datetime.now(timezone.utc)
    session.add_all([
        Agent(agent_id=1, agent_uid="agent-1", server_id=10, status_code="APPROVED"),
        Agent(agent_id=2, agent_uid="agent-2", server_id=20, status_code="APPROVED"),
        AgentStatusCurr(
            agent_id=1,
            agent_status="NORMAL",
            last_heartbeat_at=now - timedelta(minutes=3),
        ),
        AgentStatusCurr(
            agent_id=2,
            agent_status="NORMAL",
            last_heartbeat_at=now - timedelta(minutes=3),
        ),
    ])
    session.commit()
    monkeypatch.setattr(scheduler, "SessionLocal", lambda: session)
    get_count, listener = count_selects(engine)
    try:
        scheduler.check_agent_offline()
        assert get_count() == 3
        with Session(engine) as verify:
            assert verify.get(AgentStatusCurr, 1).agent_status == "OFFLINE"
            assert verify.get(AgentStatusCurr, 2).agent_status == "OFFLINE"
            assert verify.execute(select(Event).where(Event.status_code == "OPEN")).scalars().all()
    finally:
        event.remove(engine, "before_cursor_execute", listener)
        engine.dispose()



def test_oracle_in_chunks_stay_below_the_11g_expression_limit():
    chunks = list(oracle_in_chunks(list(range(ORACLE_IN_LIST_CHUNK_SIZE + 2))))
    assert [len(chunk) for chunk in chunks] == [ORACLE_IN_LIST_CHUNK_SIZE, 2]
    assert [value for chunk in chunks for value in chunk] == list(
        range(ORACLE_IN_LIST_CHUNK_SIZE + 2)
    )
