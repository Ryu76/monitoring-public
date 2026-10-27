from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, delete, text
from typing import List, Optional
from datetime import datetime, timezone

from app.api.dependencies import get_db
from app.models.server import Server, ServerStatusCurr
from app.models.agent import Agent, AgentStatusCurr
from app.models.event import Event, Incident, IncidentAction
from app.models.resource import MetricCurrent
from app.models.process import CheckTarget, CheckResultHistory

router = APIRouter()


class IncidentCreateFromEventRequest(BaseModel):
    incident_title: Optional[str] = Field(None, max_length=500)
    impact_code: Optional[str] = Field("MEDIUM", max_length=30)
    cause_code: Optional[str] = Field("UNKNOWN", max_length=30)
    assigned_to: Optional[int] = None
    action_note: Optional[str] = None


class IncidentUpdateRequest(BaseModel):
    incident_title: Optional[str] = Field(None, max_length=500)
    status_code: Optional[str] = Field(None, max_length=30)
    impact_code: Optional[str] = Field(None, max_length=30)
    cause_code: Optional[str] = Field(None, max_length=30)
    assigned_to: Optional[int] = None


class IncidentActionCreateRequest(BaseModel):
    action_note: str = Field(..., min_length=1)
    action_user_id: Optional[int] = None
    status_code: Optional[str] = Field(None, max_length=30)
    cause_code: Optional[str] = Field(None, max_length=30)
    assigned_to: Optional[int] = None


class ServerCheckTargetsRequest(BaseModel):
    processes: List[str] = []
    services: List[str] = []
    ports: List[int] = []


class ServerUpdateRequest(BaseModel):
    server_name: str = Field(..., min_length=1, max_length=100)


def next_numeric_id(db: Session, column) -> int:
    return (db.execute(select(func.max(column))).scalar() or 0) + 1


def incident_to_dict(inc: Incident, actions: Optional[List[IncidentAction]] = None):
    return {
        "incident_id": inc.incident_id,
        "incident_title": inc.incident_title,
        "status_code": inc.status_code,
        "impact_code": inc.impact_code,
        "cause_code": inc.cause_code,
        "assigned_to": inc.assigned_to,
        "detected_at": inc.detected_at.isoformat() if inc.detected_at else None,
        "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
        "closed_at": inc.closed_at.isoformat() if inc.closed_at else None,
        "created_by": inc.created_by,
        "updated_at": inc.updated_at.isoformat() if inc.updated_at else None,
        "actions": [
            {
                "action_id": action.action_id,
                "incident_id": action.incident_id,
                "action_user_id": action.action_user_id,
                "action_note": action.action_note,
                "action_at": action.action_at.isoformat() if action.action_at else None,
            }
            for action in (actions or [])
        ],
    }


def provided_fields(model: BaseModel) -> set[str]:
    return getattr(model, "model_fields_set", getattr(model, "__fields_set__", set()))


def ensure_check_target_table(db: Session):
    try:
        db.execute(text("SELECT 1 FROM mon_check_target WHERE 1 = 0"))
    except Exception:
        db.rollback()
        db.execute(text("""
            CREATE TABLE mon_check_target (
                check_target_id NUMBER NOT NULL PRIMARY KEY,
                server_id NUMBER NOT NULL,
                target_type_code VARCHAR2(30) NOT NULL,
                target_name VARCHAR2(200) NOT NULL,
                use_yn CHAR(1) DEFAULT 'Y' NOT NULL,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """))
        db.commit()


def ensure_check_result_hist_table(db: Session):
    try:
        db.execute(text("SELECT 1 FROM mon_check_result_hist WHERE 1 = 0"))
    except Exception:
        db.rollback()
        db.execute(text("""
            CREATE TABLE mon_check_result_hist (
                check_result_id NUMBER NOT NULL PRIMARY KEY,
                server_id NUMBER NOT NULL,
                agent_id NUMBER,
                target_type_code VARCHAR2(30) NOT NULL,
                target_name VARCHAR2(200) NOT NULL,
                metric_code VARCHAR2(60) NOT NULL,
                metric_value NUMBER,
                string_value VARCHAR2(1000),
                status_code VARCHAR2(30),
                collected_at TIMESTAMP NOT NULL,
                received_at TIMESTAMP NOT NULL
            )
        """))
        db.commit()


from app.domain.check_targets import normalize_names, normalize_ports, check_targets_to_dict

# ──────────────────────── Dashboard ────────────────────────

@router.get("/dashboard/summary")
def get_dashboard_summary(db: Session = Depends(get_db)):
    """대시보드 요약: 서버/에이전트/장애 현황 통합"""
    total_servers = db.execute(select(func.count(Server.server_id)).where(Server.use_yn == 'Y')).scalar() or 0

    status_counts = {}
    for status_label in ['NORMAL', 'WARNING', 'CRITICAL', 'UNKNOWN']:
        cnt = db.execute(
            select(func.count(ServerStatusCurr.server_id)).where(ServerStatusCurr.composite_status == status_label)
        ).scalar() or 0
        status_counts[status_label.lower()] = cnt

    total_agents = db.execute(select(func.count(Agent.agent_id))).scalar() or 0
    online_agents = db.execute(
        select(func.count(AgentStatusCurr.agent_id)).where(AgentStatusCurr.agent_status == 'NORMAL')
    ).scalar() or 0

    open_events = db.execute(select(func.count(Event.event_uid)).where(Event.status_code == 'OPEN')).scalar() or 0

    return {
        "success": True,
        "data": {
            "total_servers": total_servers,
            **status_counts,
            "total_agents": total_agents,
            "online_agents": online_agents,
            "open_events": open_events,
        }
    }

# ──────────────────────── Servers ────────────────────────

@router.get("/servers")
def get_servers(db: Session = Depends(get_db)):
    """서버 목록 + 종합 상태"""
    servers = db.execute(select(Server).where(Server.use_yn == 'Y')).scalars().all()
    result = []
    for s in servers:
        status = db.execute(
            select(ServerStatusCurr).where(ServerStatusCurr.server_id == s.server_id)
        ).scalar_one_or_none()
        result.append({
            "server_id": s.server_id,
            "server_uid": s.server_uid,
            "server_name": s.server_name,
            "host_name": s.host_name,
            "mgmt_ip": s.mgmt_ip,
            "os_type_code": s.os_type_code,
            "composite_status": status.composite_status if status else "UNKNOWN",
        })
    return {"success": True, "data": result}

@router.get("/servers/{server_id}")
def get_server_detail(server_id: int, db: Session = Depends(get_db)):
    """서버 상세 + 현재 지표"""
    server = db.execute(select(Server).where(Server.server_id == server_id)).scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    metrics = db.execute(
        select(MetricCurrent).where(MetricCurrent.server_id == server_id)
    ).scalars().all()

    metric_list = [
        {
            "metric_code": m.metric_code,
            "dimension_key": m.dimension_key,
            "dimension_value": m.dimension_value,
            "metric_value": m.metric_value,
            "string_value": m.string_value,
            "status_code": m.status_code,
            "collected_at": m.collected_at.isoformat() if m.collected_at else None,
        }
        for m in metrics
    ]

    agent = db.execute(select(Agent).where(Agent.server_id == server_id)).scalar_one_or_none()
    agent_status = None
    if agent:
        agent_status = db.execute(
            select(AgentStatusCurr).where(AgentStatusCurr.agent_id == agent.agent_id)
        ).scalar_one_or_none()

    last_collected_at = max(
        (m.collected_at for m in metrics if m.collected_at),
        default=None
    )

    return {
        "success": True,
        "data": {
            "server_id": server.server_id,
            "server_name": server.server_name,
            "host_name": server.host_name,
            "mgmt_ip": server.mgmt_ip,
            "os_type_code": server.os_type_code,
            "os_name": server.os_name,
            "os_version": server.os_version,
            "agent_id": agent.agent_id if agent else None,
            "agent_status": agent_status.agent_status if agent_status else "UNKNOWN",
            "last_heartbeat_at": agent_status.last_heartbeat_at.isoformat() if agent_status and agent_status.last_heartbeat_at else None,
            "last_collected_at": last_collected_at.isoformat() if last_collected_at else None,
            "metrics": metric_list,
        }
    }


@router.put("/servers/{server_id}")
def update_server(server_id: int, req: ServerUpdateRequest, db: Session = Depends(get_db)):
    server = db.execute(select(Server).where(Server.server_id == server_id)).scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    server.server_name = req.server_name.strip()
    server.updated_at = datetime.now(timezone.utc)
    server.updated_by = "WEB"
    db.commit()
    return {
        "success": True,
        "data": {
            "server_id": server.server_id,
            "server_uid": server.server_uid,
            "server_name": server.server_name,
            "host_name": server.host_name,
            "mgmt_ip": server.mgmt_ip,
            "os_type_code": server.os_type_code,
        },
    }


@router.get("/servers/{server_id}/check-targets")
def get_server_check_targets(server_id: int, db: Session = Depends(get_db)):
    ensure_check_target_table(db)
    server = db.execute(select(Server).where(Server.server_id == server_id)).scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    items = db.execute(
        select(CheckTarget)
        .where(CheckTarget.server_id == server_id, CheckTarget.use_yn == "Y")
        .order_by(CheckTarget.target_type_code, CheckTarget.target_name)
    ).scalars().all()
    return {"success": True, "data": check_targets_to_dict(items)}


@router.put("/servers/{server_id}/check-targets")
def update_server_check_targets(
    server_id: int,
    req: ServerCheckTargetsRequest,
    db: Session = Depends(get_db),
):
    ensure_check_target_table(db)
    server = db.execute(select(Server).where(Server.server_id == server_id)).scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    now = datetime.now(timezone.utc)
    db.execute(delete(CheckTarget).where(CheckTarget.server_id == server_id))

    next_id = next_numeric_id(db, CheckTarget.check_target_id)
    rows = []
    for target_type, values in (
        ("PROCESS", normalize_names(req.processes)),
        ("SERVICE", normalize_names(req.services)),
        ("PORT", normalize_ports(req.ports)),
    ):
        for target_name in values:
            rows.append(CheckTarget(
                check_target_id=next_id,
                server_id=server_id,
                target_type_code=target_type,
                target_name=target_name,
                use_yn="Y",
                created_at=now,
                updated_at=now,
            ))
            next_id += 1

    db.add_all(rows)
    db.commit()

    items = db.execute(
        select(CheckTarget)
        .where(CheckTarget.server_id == server_id, CheckTarget.use_yn == "Y")
        .order_by(CheckTarget.target_type_code, CheckTarget.target_name)
    ).scalars().all()
    return {"success": True, "data": check_targets_to_dict(items)}


@router.get("/servers/{server_id}/check-history")
def get_server_check_history(
    server_id: int,
    target_type_code: Optional[str] = None,
    target_name: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    ensure_check_result_hist_table(db)
    server = db.execute(select(Server).where(Server.server_id == server_id)).scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    limit = max(1, min(limit, 500))
    stmt = select(CheckResultHistory).where(CheckResultHistory.server_id == server_id)
    if target_type_code:
        stmt = stmt.where(CheckResultHistory.target_type_code == target_type_code)
    if target_name:
        stmt = stmt.where(CheckResultHistory.target_name == target_name)
    rows = db.execute(
        stmt.order_by(CheckResultHistory.collected_at.desc()).limit(limit)
    ).scalars().all()

    return {
        "success": True,
        "data": [
            {
                "check_result_id": row.check_result_id,
                "server_id": row.server_id,
                "agent_id": row.agent_id,
                "target_type_code": row.target_type_code,
                "target_name": row.target_name,
                "metric_code": row.metric_code,
                "metric_value": row.metric_value,
                "string_value": row.string_value,
                "status_code": row.status_code,
                "collected_at": row.collected_at.isoformat() if row.collected_at else None,
                "received_at": row.received_at.isoformat() if row.received_at else None,
            }
            for row in rows
        ],
    }

# ──────────────────────── Agents ────────────────────────

@router.get("/agents")
def get_agents(db: Session = Depends(get_db)):
    """에이전트 목록 + 현재 상태"""
    agents = db.execute(select(Agent)).scalars().all()
    result = []
    for a in agents:
        status = db.execute(
            select(AgentStatusCurr).where(AgentStatusCurr.agent_id == a.agent_id)
        ).scalar_one_or_none()
        server = db.execute(
            select(Server).where(Server.server_id == a.server_id)
        ).scalar_one_or_none()
        result.append({
            "agent_id": a.agent_id,
            "agent_uid": a.agent_uid,
            "server_id": a.server_id,
            "host_name": server.host_name if server else None,
            "mgmt_ip": server.mgmt_ip if server else None,
            "status_code": a.status_code,
            "agent_version": a.agent_version,
            "agent_status": status.agent_status if status else "UNKNOWN",
            "last_heartbeat_at": status.last_heartbeat_at.isoformat() if status and status.last_heartbeat_at else None,
        })
    return {"success": True, "data": result}

@router.put("/agents/{agent_id}/approve")
def approve_agent(agent_id: int, db: Session = Depends(get_db)):
    """에이전트 승인"""
    agent = db.execute(select(Agent).where(Agent.agent_id == agent_id)).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.status_code = 'APPROVED'
    agent.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"success": True, "message": f"Agent {agent_id} approved"}

@router.put("/agents/{agent_id}/revoke")
def revoke_agent(agent_id: int, db: Session = Depends(get_db)):
    """에이전트 차단"""
    agent = db.execute(select(Agent).where(Agent.agent_id == agent_id)).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.status_code = 'REVOKED'
    agent.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"success": True, "message": f"Agent {agent_id} revoked"}

# ──────────────────────── Events ────────────────────────

@router.get("/events")
def get_events(status: Optional[str] = None, db: Session = Depends(get_db)):
    """이벤트(장애) 목록 조회"""
    stmt = select(Event)
    if status:
        stmt = stmt.where(Event.status_code == status)
    events = db.execute(stmt).scalars().all()
    result = []
    for e in events:
        result.append({
            "event_uid": e.event_uid,
            "rule_id": e.rule_id,
            "server_id": e.server_id,
            "target_type_code": e.target_type_code,
            "severity_code": e.severity_code,
            "status_code": e.status_code,
            "title": e.title,
            "message": e.message,
            "first_occurred_at": e.first_occurred_at.isoformat() if e.first_occurred_at else None,
            "last_occurred_at": e.last_occurred_at.isoformat() if e.last_occurred_at else None,
            "recovered_at": e.recovered_at.isoformat() if e.recovered_at else None,
            "occurrence_count": e.occurrence_count,
            "ack_at": e.ack_at.isoformat() if e.ack_at else None,
            "incident_id": e.incident_id,
        })
    return {"success": True, "data": result}

@router.put("/events/{event_uid}/ack")
def ack_event(event_uid: str, db: Session = Depends(get_db)):
    """이벤트 확인(Acknowledge) 처리"""
    evt = db.execute(select(Event).where(Event.event_uid == event_uid)).scalar_one_or_none()
    if not evt:
        raise HTTPException(status_code=404, detail="Event not found")
    evt.ack_at = datetime.now(timezone.utc)
    db.commit()
    return {"success": True, "message": f"Event {event_uid} acknowledged"}


@router.post("/events/{event_uid}/incident")
def create_incident_from_event(
    event_uid: str,
    req: IncidentCreateFromEventRequest,
    db: Session = Depends(get_db),
):
    """Create an incident from an event and link them."""
    evt = db.execute(select(Event).where(Event.event_uid == event_uid)).scalar_one_or_none()
    if not evt:
        raise HTTPException(status_code=404, detail="Event not found")

    if evt.incident_id:
        inc = db.execute(select(Incident).where(Incident.incident_id == evt.incident_id)).scalar_one_or_none()
        if inc:
            actions = db.execute(
                select(IncidentAction)
                .where(IncidentAction.incident_id == inc.incident_id)
                .order_by(IncidentAction.action_at.desc())
            ).scalars().all()
            return {"success": True, "data": incident_to_dict(inc, actions), "message": "Incident already linked"}

    now = datetime.now(timezone.utc)
    incident_id = next_numeric_id(db, Incident.incident_id)
    inc = Incident(
        incident_id=incident_id,
        incident_title=req.incident_title or evt.title,
        status_code="OPEN",
        impact_code=req.impact_code or "MEDIUM",
        cause_code=req.cause_code or "UNKNOWN",
        assigned_to=req.assigned_to,
        detected_at=evt.first_occurred_at or now,
        created_by="WEB",
        updated_at=now,
    )
    db.add(inc)
    evt.incident_id = incident_id

    note = req.action_note or f"이벤트에서 인시던트 생성: {evt.title}"
    action = IncidentAction(
        action_id=next_numeric_id(db, IncidentAction.action_id),
        incident_id=incident_id,
        action_user_id=req.assigned_to,
        action_note=note,
        action_at=now,
    )
    db.add(action)
    db.commit()

    return {"success": True, "data": incident_to_dict(inc, [action])}

# ──────────────────────── Incidents ────────────────────────

@router.get("/incidents")
def get_incidents(db: Session = Depends(get_db)):
    """장애 인시던트 목록 조회"""
    incidents = db.execute(select(Incident)).scalars().all()
    result = []
    for inc in incidents:
        latest_action = db.execute(
            select(IncidentAction)
            .where(IncidentAction.incident_id == inc.incident_id)
            .order_by(IncidentAction.action_at.desc())
        ).scalars().first()
        item = incident_to_dict(inc)
        item["latest_action_note"] = latest_action.action_note if latest_action else None
        item["latest_action_at"] = latest_action.action_at.isoformat() if latest_action and latest_action.action_at else None
        result.append(item)
    return {"success": True, "data": result}


@router.get("/incidents/{incident_id}")
def get_incident_detail(incident_id: int, db: Session = Depends(get_db)):
    inc = db.execute(select(Incident).where(Incident.incident_id == incident_id)).scalar_one_or_none()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    actions = db.execute(
        select(IncidentAction)
        .where(IncidentAction.incident_id == incident_id)
        .order_by(IncidentAction.action_at.desc())
    ).scalars().all()
    events = db.execute(select(Event).where(Event.incident_id == incident_id)).scalars().all()
    data = incident_to_dict(inc, actions)
    data["events"] = [
        {
            "event_uid": evt.event_uid,
            "severity_code": evt.severity_code,
            "status_code": evt.status_code,
            "title": evt.title,
            "message": evt.message,
            "first_occurred_at": evt.first_occurred_at.isoformat() if evt.first_occurred_at else None,
        }
        for evt in events
    ]
    return {"success": True, "data": data}


@router.put("/incidents/{incident_id}")
def update_incident(
    incident_id: int,
    req: IncidentUpdateRequest,
    db: Session = Depends(get_db),
):
    inc = db.execute(select(Incident).where(Incident.incident_id == incident_id)).scalar_one_or_none()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    now = datetime.now(timezone.utc)
    if req.incident_title is not None:
        inc.incident_title = req.incident_title
    if req.status_code is not None:
        inc.status_code = req.status_code
        if req.status_code in ("RESOLVED", "CLOSED") and not inc.resolved_at:
            inc.resolved_at = now
        if req.status_code == "CLOSED" and not inc.closed_at:
            inc.closed_at = now
    if req.impact_code is not None:
        inc.impact_code = req.impact_code
    if req.cause_code is not None:
        inc.cause_code = req.cause_code
    if "assigned_to" in provided_fields(req):
        inc.assigned_to = req.assigned_to
    inc.updated_at = now
    db.commit()
    return {"success": True, "data": incident_to_dict(inc)}


@router.post("/incidents/{incident_id}/actions")
def add_incident_action(
    incident_id: int,
    req: IncidentActionCreateRequest,
    db: Session = Depends(get_db),
):
    inc = db.execute(select(Incident).where(Incident.incident_id == incident_id)).scalar_one_or_none()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    now = datetime.now(timezone.utc)
    if req.status_code:
        inc.status_code = req.status_code
        if req.status_code in ("RESOLVED", "CLOSED") and not inc.resolved_at:
            inc.resolved_at = now
        if req.status_code == "CLOSED" and not inc.closed_at:
            inc.closed_at = now
    if req.cause_code:
        inc.cause_code = req.cause_code
    if req.assigned_to is not None:
        inc.assigned_to = req.assigned_to
    inc.updated_at = now

    action = IncidentAction(
        action_id=next_numeric_id(db, IncidentAction.action_id),
        incident_id=incident_id,
        action_user_id=req.action_user_id,
        action_note=req.action_note,
        action_at=now,
    )
    db.add(action)
    db.commit()
    return {"success": True, "data": incident_to_dict(inc, [action])}
