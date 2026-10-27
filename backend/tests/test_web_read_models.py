from datetime import datetime, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.agent import Agent, AgentStatusCurr
from app.models.event import Event
from app.models.server import Server, ServerStatusCurr
from app.services.web_read_models import agent_list, dashboard_summary, server_list


def make_session() -> tuple[Session, object]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            Server.__table__,
            ServerStatusCurr.__table__,
            Agent.__table__,
            AgentStatusCurr.__table__,
            Event.__table__,
        ],
    )
    session = Session(engine)
    now = datetime.now(timezone.utc)
    for index, status in enumerate(("NORMAL", "WARNING", "CRITICAL"), start=1):
        session.add(Server(
            server_id=index,
            server_uid=f"server-{index}",
            server_name=f"server-{index}",
            host_name=f"host-{index}",
            mgmt_ip=f"10.0.0.{index}",
            os_type_code="LINUX",
            server_group="ops",
            tags="prod,ops",
            use_yn="Y",
        ))
        session.add(ServerStatusCurr(server_id=index, composite_status=status))
        session.add(Agent(
            agent_id=index,
            agent_uid=f"agent-{index}",
            server_id=index,
            status_code="APPROVED",
            agent_version="1.0.0",
        ))
        session.add(AgentStatusCurr(
            agent_id=index,
            agent_status="NORMAL" if index == 1 else "WARNING",
            last_heartbeat_at=now,
        ))
    session.add(Event(
        event_uid="event-open",
        severity_code="CRITICAL",
        status_code="OPEN",
        title="open event",
        first_occurred_at=now,
    ))
    session.commit()
    return session, engine


def count_statements(engine):
    count = 0

    def listener(*_args):
        nonlocal count
        count += 1

    event.listen(engine, "before_cursor_execute", listener)
    return lambda: count, listener


def test_server_list_uses_one_query_for_multiple_servers():
    session, engine = make_session()
    get_count, listener = count_statements(engine)
    try:
        result = server_list(session, server_group="ops", tags="prod")
        assert get_count() == 1
        assert [row["composite_status"] for row in result] == ["NORMAL", "WARNING", "CRITICAL"]
    finally:
        event.remove(engine, "before_cursor_execute", listener)
        session.close()
        engine.dispose()


def test_agent_list_uses_one_query_for_multiple_agents():
    session, engine = make_session()
    get_count, listener = count_statements(engine)
    try:
        result = agent_list(session)
        assert get_count() == 1
        assert result[0]["host_name"] == "host-1"
        assert result[0]["agent_status"] == "NORMAL"
    finally:
        event.remove(engine, "before_cursor_execute", listener)
        session.close()
        engine.dispose()


def test_dashboard_summary_uses_bounded_query_count_and_preserves_contract():
    session, engine = make_session()
    get_count, listener = count_statements(engine)
    try:
        result = dashboard_summary(session)
        assert get_count() == 1
        assert result == {
            "total_servers": 3,
            "normal": 1,
            "warning": 1,
            "critical": 1,
            "unknown": 0,
            "total_agents": 3,
            "online_agents": 1,
            "open_events": 1,
        }
    finally:
        event.remove(engine, "before_cursor_execute", listener)
        session.close()
        engine.dispose()
