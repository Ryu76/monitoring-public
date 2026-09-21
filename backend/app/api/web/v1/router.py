from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, delete, text
from typing import List, Optional
from datetime import datetime, timezone

from app.api.dependencies import get_db, get_current_user, require_roles
from app.models.server import Server, ServerStatusCurr
from app.models.agent import Agent, AgentStatusCurr
from app.models.event import Event, Incident, IncidentAction
from app.models.resource import MetricCurrent
from app.models.process import CheckTarget, CheckResultHistory
from app.domain.check_targets import normalize_names, normalize_ports, check_targets_to_dict
from app.services.web_read_models import agent_list, dashboard_summary, server_list

router = APIRouter(dependencies=[Depends(get_current_user)])


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
    server_group: Optional[str] = Field(None, max_length=100)
    tags: Optional[str] = Field(None, max_length=500)





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



# ──────────────────────── Dashboard ────────────────────────

@router.get("/dashboard/summary")
def get_dashboard_summary(db: Session = Depends(get_db)):
    """대시보드 요약: 서버/에이전트/장애 현황 통합"""
    return {"success": True, "data": dashboard_summary(db)}

# ──────────────────────── Servers ────────────────────────

@router.get("/servers")
def get_servers(
    server_group: Optional[str] = None,
    tags: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """서버 목록 + 종합 상태 (그룹/태그 필터링 지원)"""
    return {
        "success": True,
        "data": server_list(db, server_group=server_group, tags=tags),
    }

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
            "server_group": server.server_group,
            "tags": server.tags,
            "agent_id": agent.agent_id if agent else None,
            "agent_status": agent_status.agent_status if agent_status else "UNKNOWN",
            "last_heartbeat_at": agent_status.last_heartbeat_at.isoformat() if agent_status and agent_status.last_heartbeat_at else None,
            "last_collected_at": last_collected_at.isoformat() if last_collected_at else None,
            "metrics": metric_list,
        }
    }


from fastapi import Request
from app.core.audit import log_audit, get_client_ip
from app.models.system import SysUser

@router.put("/servers/{server_id}", dependencies=[Depends(require_roles(["ADMIN", "OPERATOR"]))])
def update_server(
    server_id: int,
    req: ServerUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    server = db.execute(select(Server).where(Server.server_id == server_id)).scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    before_data = {
        "server_name": server.server_name,
        "server_group": server.server_group,
        "tags": server.tags
    }
    server.server_name = req.server_name.strip()
    if "server_group" in provided_fields(req):
        server.server_group = req.server_group
    if "tags" in provided_fields(req):
        server.tags = req.tags
    server.updated_at = datetime.now(timezone.utc)
    server.updated_by = current_user.login_id
    after_data = {
        "server_name": server.server_name,
        "server_group": server.server_group,
        "tags": server.tags
    }

    log_audit(
        db=db,
        user_id=current_user.user_id,
        action_type="UPDATE",
        target_entity="Server",
        target_id=str(server.server_id),
        before_data=before_data,
        after_data=after_data,
        ip_address=get_client_ip(request)
    )

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
            "server_group": server.server_group,
            "tags": server.tags
        },
    }


@router.get("/servers/{server_id}/check-targets")
def get_server_check_targets(server_id: int, db: Session = Depends(get_db)):
    pass
    server = db.execute(select(Server).where(Server.server_id == server_id)).scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    items = db.execute(
        select(CheckTarget)
        .where(CheckTarget.server_id == server_id, CheckTarget.use_yn == "Y")
        .order_by(CheckTarget.target_type_code, CheckTarget.target_name)
    ).scalars().all()
    return {"success": True, "data": check_targets_to_dict(items)}


@router.put("/servers/{server_id}/check-targets", dependencies=[Depends(require_roles(["ADMIN", "OPERATOR"]))])
def update_server_check_targets(
    server_id: int,
    req: ServerCheckTargetsRequest,
    db: Session = Depends(get_db),
):
    pass
    server = db.execute(select(Server).where(Server.server_id == server_id)).scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    now = datetime.now(timezone.utc)
    db.execute(delete(CheckTarget).where(CheckTarget.server_id == server_id))

    rows = []
    for target_type, values in (
        ("PROCESS", normalize_names(req.processes)),
        ("SERVICE", normalize_names(req.services)),
        ("PORT", normalize_ports(req.ports)),
    ):
        for target_name in values:
            rows.append(CheckTarget(
                server_id=server_id,
                target_type_code=target_type,
                target_name=target_name,
                use_yn="Y",
                created_at=now,
                updated_at=now,
            ))

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
    pass
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

@router.get("/servers/{server_id}/metrics/{metric_code}/history")
def get_server_metric_history(
    server_id: int,
    metric_code: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    dimension_key: str = "-",
    dimension_value: str = "-",
    limit: int = 1000,
    db: Session = Depends(get_db)
):
    from app.models.resource import MetricHistory

    # Range limit
    if not end_time:
        end_time = datetime.now(timezone.utc)
    if not start_time:
        from datetime import timedelta
        start_time = end_time - timedelta(days=7)

    if (end_time - start_time).days > 30:
        raise HTTPException(status_code=400, detail="Range cannot exceed 30 days")

    limit = max(1, min(limit, 5000))

    stmt = (
        select(MetricHistory)
        .where(
            MetricHistory.server_id == server_id,
            MetricHistory.metric_code == metric_code,
            MetricHistory.dimension_key == dimension_key,
            MetricHistory.dimension_value == dimension_value,
            MetricHistory.collected_at >= start_time,
            MetricHistory.collected_at <= end_time
        )
        .order_by(MetricHistory.collected_at.asc())
        .limit(limit)
    )

    try:
        rows = db.execute(stmt).scalars().all()
    except Exception as e:
        # If partition issues or table doesn't exist during dev
        db.rollback()
        rows = []

    return {
        "success": True,
        "data": [
            {
                "metric_value": row.metric_value,
                "collected_at": row.collected_at.isoformat() if row.collected_at else None
            }
            for row in rows
        ]
    }

# ──────────────────────── Agents ────────────────────────

@router.get("/agents")
def get_agents(db: Session = Depends(get_db)):
    """에이전트 목록 + 현재 상태"""
    return {"success": True, "data": agent_list(db)}

@router.put("/agents/{agent_id}/approve", dependencies=[Depends(require_roles(["ADMIN"]))])
def approve_agent(agent_id: int, db: Session = Depends(get_db)):
    """에이전트 승인"""
    agent = db.execute(select(Agent).where(Agent.agent_id == agent_id)).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.status_code = 'APPROVED'
    agent.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"success": True, "message": f"Agent {agent_id} approved"}

@router.put("/agents/{agent_id}/revoke", dependencies=[Depends(require_roles(["ADMIN"]))])
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

@router.put("/events/{event_uid}/ack", dependencies=[Depends(require_roles(["ADMIN", "OPERATOR"]))])
def ack_event(event_uid: str, db: Session = Depends(get_db)):
    """이벤트 확인(Acknowledge) 처리"""
    evt = db.execute(select(Event).where(Event.event_uid == event_uid)).scalar_one_or_none()
    if not evt:
        raise HTTPException(status_code=404, detail="Event not found")
    evt.ack_at = datetime.now(timezone.utc)
    db.commit()
    return {"success": True, "message": f"Event {event_uid} acknowledged"}


@router.post("/events/{event_uid}/incident", dependencies=[Depends(require_roles(["ADMIN", "OPERATOR"]))])
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
    inc = Incident(
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
    db.flush()
    evt.incident_id = inc.incident_id

    note = req.action_note or f"이벤트에서 인시던트 생성: {evt.title}"
    action = IncidentAction(
        incident_id=inc.incident_id,
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


@router.put("/incidents/{incident_id}", dependencies=[Depends(require_roles(["ADMIN", "OPERATOR"]))])
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
        if req.status_code == "OPEN":
            inc.resolved_at = None
            inc.closed_at = None
    if req.impact_code is not None:
        inc.impact_code = req.impact_code
    if req.cause_code is not None:
        inc.cause_code = req.cause_code
    if "assigned_to" in provided_fields(req):
        inc.assigned_to = req.assigned_to
    inc.updated_at = now
    db.commit()
    return {"success": True, "data": incident_to_dict(inc)}


@router.post("/incidents/{incident_id}/actions", dependencies=[Depends(require_roles(["ADMIN", "OPERATOR"]))])
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
        if req.status_code == "OPEN":
            inc.resolved_at = None
            inc.closed_at = None
    if req.cause_code:
        inc.cause_code = req.cause_code
    if req.assigned_to is not None:
        inc.assigned_to = req.assigned_to
    inc.updated_at = now

    action = IncidentAction(
        incident_id=incident_id,
        action_user_id=req.action_user_id,
        action_note=req.action_note,
        action_at=now,
    )
    db.add(action)
    db.commit()
    return {"success": True, "data": incident_to_dict(inc, [action])}
