from __future__ import annotations

from typing import Optional

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.agent import Agent, AgentStatusCurr
from app.models.event import Event
from app.models.server import Server, ServerStatusCurr


STATUS_LABELS = ("NORMAL", "WARNING", "CRITICAL", "UNKNOWN")


def dashboard_summary(db: Session) -> dict[str, int]:
    """Return dashboard aggregates in one statement without a cross join."""
    status_counts = [
        select(
            func.coalesce(
                func.sum(case((ServerStatusCurr.composite_status == label, 1), else_=0)),
                0,
            )
        ).scalar_subquery().label(label.lower())
        for label in STATUS_LABELS
    ]
    agent_from = Agent.__table__.outerjoin(
        AgentStatusCurr.__table__, AgentStatusCurr.agent_id == Agent.agent_id
    )
    row = db.execute(
        select(
            select(func.count(Server.server_id))
            .where(Server.use_yn == "Y")
            .scalar_subquery()
            .label("total_servers"),
            *status_counts,
            select(func.count(Agent.agent_id))
            .select_from(agent_from)
            .scalar_subquery()
            .label("total_agents"),
            select(
                func.coalesce(
                    func.sum(case((AgentStatusCurr.agent_status == "NORMAL", 1), else_=0)),
                    0,
                )
            )
            .select_from(agent_from)
            .scalar_subquery()
            .label("online_agents"),
            select(func.count(Event.event_uid))
            .where(Event.status_code == "OPEN")
            .scalar_subquery()
            .label("open_events"),
        )
    ).mappings().one()
    return dict(row)


def server_list(
    db: Session,
    *,
    server_group: Optional[str] = None,
    tags: Optional[str] = None,
) -> list[dict[str, object]]:
    stmt = select(Server, ServerStatusCurr.composite_status).outerjoin(
        ServerStatusCurr, ServerStatusCurr.server_id == Server.server_id
    ).where(Server.use_yn == "Y")
    if server_group:
        stmt = stmt.where(Server.server_group == server_group)
    if tags:
        stmt = stmt.where(Server.tags.like(f"%{tags}%"))
    stmt = stmt.order_by(Server.server_id)
    return [
        {
            "server_id": server.server_id,
            "server_uid": server.server_uid,
            "server_name": server.server_name,
            "host_name": server.host_name,
            "mgmt_ip": server.mgmt_ip,
            "os_type_code": server.os_type_code,
            "server_group": server.server_group,
            "tags": server.tags,
            "composite_status": composite_status or "UNKNOWN",
        }
        for server, composite_status in db.execute(stmt).all()
    ]


def agent_list(db: Session) -> list[dict[str, object]]:
    stmt = select(
        Agent,
        AgentStatusCurr.agent_status,
        AgentStatusCurr.last_heartbeat_at,
        Server.host_name,
        Server.mgmt_ip,
    ).outerjoin(
        AgentStatusCurr, AgentStatusCurr.agent_id == Agent.agent_id
    ).outerjoin(
        Server, Server.server_id == Agent.server_id
    ).order_by(Agent.agent_id)
    return [
        {
            "agent_id": agent.agent_id,
            "agent_uid": agent.agent_uid,
            "server_id": agent.server_id,
            "host_name": host_name,
            "mgmt_ip": mgmt_ip,
            "status_code": agent.status_code,
            "agent_version": agent.agent_version,
            "agent_status": agent_status or "UNKNOWN",
            "last_heartbeat_at": last_heartbeat_at.isoformat() if last_heartbeat_at else None,
        }
        for agent, agent_status, last_heartbeat_at, host_name, mgmt_ip in db.execute(stmt).all()
    ]
