"""Agent API v1 라우터 - 등록, 하트비트, 지표 수신, 설정 조회"""

import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func, delete, text

from app.api.dependencies import get_db, verify_agent
from app.models.server import Server, ServerStatusCurr
from app.models.agent import Agent, AgentHeartbeatHist, AgentStatusCurr
from app.models.resource import MetricCurrent, MetricHistory, MetricDef
from app.models.process import CheckTarget, CheckResultHistory
from app.schemas.agent import (
    AgentEnrollRequest, AgentEnrollResponse,
    HeartbeatRequest, HeartbeatResponse,
    MetricBulkRequest, MetricBulkResponse,
    AgentConfigResponse, AgentConfigData,
)

logger = logging.getLogger(__name__)
router = APIRouter()

METRIC_DEFINITIONS = {
    "CPU_USAGE_PCT": ("CPU Usage (%)", "CPU", "FLOAT", "PERCENT", "AVG"),
    "MEM_USAGE_PCT": ("Memory Usage (%)", "MEMORY", "FLOAT", "PERCENT", "AVG"),
    "MEM_AVAILABLE_BYTES": ("Memory Available (Bytes)", "MEMORY", "BIGINT", "BYTES", "AVG"),
    "DISK_USAGE_PCT": ("Disk Usage (%)", "DISK", "FLOAT", "PERCENT", "AVG"),
    "DISK_AVAILABLE_BYTES": ("Disk Available (Bytes)", "DISK", "BIGINT", "BYTES", "AVG"),
    "NET_BYTES_SENT": ("Network Bytes Sent", "NETWORK", "BIGINT", "BYTES", "SUM"),
    "NET_BYTES_RECV": ("Network Bytes Received", "NETWORK", "BIGINT", "BYTES", "SUM"),
    "PROCESS_CPU_PCT": ("Top Process CPU Usage (%)", "PROCESS", "FLOAT", "PERCENT", "AVG"),
    "PROCESS_MEM_PCT": ("Top Process Memory Usage (%)", "PROCESS", "FLOAT", "PERCENT", "AVG"),
    "PROCESS_STATUS": ("Process Running Status", "PROCESS", "FLOAT", "BOOLEAN", "LAST"),
    "PORT_LISTEN": ("TCP Port Listening Status", "PORT", "FLOAT", "BOOLEAN", "LAST"),
    "SERVICE_STATUS": ("Service Running Status", "SERVICE", "FLOAT", "BOOLEAN", "LAST"),
}

REPLACE_SET_METRICS = {"PROCESS_CPU_PCT", "PROCESS_MEM_PCT", "PROCESS_STATUS", "PORT_LISTEN", "SERVICE_STATUS"}
CHECK_RESULT_METRICS = {
    "PROCESS_STATUS": "PROCESS",
    "SERVICE_STATUS": "SERVICE",
    "PORT_LISTEN": "PORT",
}


def ensure_metric_def(db: Session, metric_code: str):
    existing = db.get(MetricDef, metric_code)
    if existing:
        return

    metric_name, category, value_type, unit, agg_type = METRIC_DEFINITIONS.get(
        metric_code,
        (metric_code, "CUSTOM", "FLOAT", "COUNT", "LAST")
    )
    db.add(MetricDef(
        metric_code=metric_code,
        metric_name=metric_name,
        category_code=category,
        value_type_code=value_type,
        unit_code=unit,
        agg_type_code=agg_type,
        windows_support_yn="Y",
        linux_support_yn="Y",
        use_yn="Y",
        created_at=datetime.now(timezone.utc),
    ))
    db.flush()


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


def next_check_result_id(db: Session) -> int:
    return (db.execute(select(func.max(CheckResultHistory.check_result_id))).scalar() or 0) + 1


def build_agent_config(agent: Agent, db: Session) -> AgentConfigData:
    ensure_check_target_table(db)
    items = db.execute(
        select(CheckTarget)
        .where(CheckTarget.server_id == agent.server_id, CheckTarget.use_yn == "Y")
    ).scalars().all()
    processes = [i.target_name for i in items if i.target_type_code == "PROCESS"]
    services = [i.target_name for i in items if i.target_type_code == "SERVICE"]
    ports = [
        int(i.target_name)
        for i in items
        if i.target_type_code == "PORT" and str(i.target_name).isdigit()
    ]

    return AgentConfigData(
        collect_interval_sec=30,
        heartbeat_interval_sec=60,
        metrics_batch_size=100,
        enabled_collectors=["cpu", "memory", "disk", "network", "process"],
        check_processes=processes,
        check_services=services,
        check_ports=ports,
    )


# ──────────────────────────────────────────────
# POST /enroll  - Agent 최초 등록 (인증 불요)
# ──────────────────────────────────────────────

@router.post("/enroll", response_model=AgentEnrollResponse, status_code=status.HTTP_201_CREATED)
def enroll_agent(
    req: AgentEnrollRequest,
    db: Session = Depends(get_db),
):
    """
    Agent 최초 등록.
    - 동일한 host_name 및 mgmt_ip를 가진 서버가 이미 존재한다면, 기존 서버 정보를 재사용하고 Agent 정보를 연결/업데이트합니다.
    - 그렇지 않다면 mon_server 및 mon_agent에 새로운 레코드를 삽입합니다.
    - 등록/업데이트 후 에이전트의 상태는 'PENDING'으로 설정되며 관리자 승인 대기 상태가 됩니다.
    """
    now = datetime.now(timezone.utc)
    agent_uid = str(uuid.uuid4())

    try:
        # 동일한 host_name과 mgmt_ip를 가진 서버가 존재하는지 확인
        stmt = select(Server).where(
            Server.host_name == req.host_name,
            Server.mgmt_ip == req.mgmt_ip
        )
        existing_server = db.execute(stmt).scalar_one_or_none()

        if existing_server:
            # 1) 기존 서버 사용 및 정보 업데이트
            server_uid = existing_server.server_uid
            server_id = existing_server.server_id

            existing_server.service_ip = req.service_ip
            existing_server.os_type_code = req.os_type_code
            existing_server.os_name = req.os_name
            existing_server.os_version = req.os_version
            existing_server.use_yn = 'Y'
            existing_server.updated_at = now
            existing_server.updated_by = 'AGENT_ENROLL'

            # 2) 해당 서버에 기존 에이전트가 등록되어 있는지 확인
            stmt_agent = select(Agent).where(Agent.server_id == server_id)
            existing_agent = db.execute(stmt_agent).scalar_one_or_none()

            if existing_agent:
                # 기존 에이전트 정보 및 UID 업데이트 (자동 승인 상태 'APPROVED')
                existing_agent.agent_uid = agent_uid
                existing_agent.agent_version = req.agent_version
                existing_agent.install_path = req.install_path
                existing_agent.run_account = req.run_account
                existing_agent.status_code = 'APPROVED'
                existing_agent.started_at = now
                existing_agent.last_connected_at = now
                existing_agent.updated_at = now
                
                agent_id = existing_agent.agent_id
            else:
                # 신규 에이전트 생성 후 기존 서버와 연결 (자동 승인 상태 'APPROVED')
                new_agent = Agent(
                    agent_uid=agent_uid,
                    server_id=server_id,
                    agent_version=req.agent_version,
                    install_path=req.install_path,
                    run_account=req.run_account,
                    status_code='APPROVED',
                    started_at=now,
                    last_connected_at=now,
                    auto_update_yn='N',
                    created_at=now,
                    updated_at=now,
                )
                db.add(new_agent)
                db.flush()
                agent_id = new_agent.agent_id

            # 3) 서버 상태 현황 확인 및 업데이트 (UNKNOWN)
            stmt_srv_status = select(ServerStatusCurr).where(ServerStatusCurr.server_id == server_id)
            srv_status = db.execute(stmt_srv_status).scalar_one_or_none()
            if srv_status:
                srv_status.composite_status = 'UNKNOWN'
                srv_status.reason_msg = '에이전트 재등록 - 정상 가동 중'
                srv_status.last_updated_at = now
            else:
                new_srv_status = ServerStatusCurr(
                    server_id=server_id,
                    composite_status='UNKNOWN',
                    reason_msg='에이전트 재등록 - 정상 가동 중',
                    last_updated_at=now,
                )
                db.add(new_srv_status)

            # 4) 에이전트 상태 현황 확인 및 업데이트 (NORMAL)
            stmt_agent_status = select(AgentStatusCurr).where(AgentStatusCurr.agent_id == agent_id)
            agent_status = db.execute(stmt_agent_status).scalar_one_or_none()
            if agent_status:
                agent_status.agent_status = 'NORMAL'
                agent_status.delay_ms = 0
                agent_status.local_queue_count = 0
                agent_status.last_heartbeat_at = now
            else:
                new_agent_status = AgentStatusCurr(
                    agent_id=agent_id,
                    agent_status='NORMAL',
                    delay_ms=0,
                    local_queue_count=0,
                    last_heartbeat_at=now,
                )
                db.add(new_agent_status)
        else:
            # 1) 신규 서버 등록
            server_uid = str(uuid.uuid4())
            new_server = Server(
                server_uid=server_uid,
                server_name=req.host_name,
                host_name=req.host_name,
                mgmt_ip=req.mgmt_ip,
                service_ip=req.service_ip,
                os_type_code=req.os_type_code,
                os_name=req.os_name,
                os_version=req.os_version,
                use_yn='Y',
                created_at=now,
                created_by='AGENT_ENROLL',
            )
            db.add(new_server)
            db.flush()
            server_id = new_server.server_id

            # 2) 신규 에이전트 등록 (자동 승인 상태 'APPROVED')
            new_agent = Agent(
                agent_uid=agent_uid,
                server_id=server_id,
                agent_version=req.agent_version,
                install_path=req.install_path,
                run_account=req.run_account,
                status_code='APPROVED',
                started_at=now,
                last_connected_at=now,
                auto_update_yn='N',
                created_at=now,
                updated_at=now,
            )
            db.add(new_agent)
            db.flush()
            agent_id = new_agent.agent_id

            # 3) 신규 서버 상태 현황 (UNKNOWN)
            new_srv_status = ServerStatusCurr(
                server_id=server_id,
                composite_status='UNKNOWN',
                reason_msg='에이전트 등록 직후 - 정상 가동 중',
                last_updated_at=now,
            )
            db.add(new_srv_status)

            # 4) 신규 에이전트 상태 현황 (NORMAL)
            new_agent_status = AgentStatusCurr(
                agent_id=agent_id,
                agent_status='NORMAL',
                delay_ms=0,
                local_queue_count=0,
                last_heartbeat_at=now,
            )
            db.add(new_agent_status)

        db.commit()

        logger.info(
            "Agent enrolled: agent_uid=%s, server_uid=%s, server_id=%d, agent_id=%d",
            agent_uid, server_uid, server_id, agent_id
        )

        return AgentEnrollResponse(
            success=True,
            code="ENROLLED",
            message="에이전트가 등록되었습니다.",
            data={
                "agent_uid": agent_uid,
                "server_uid": server_uid,
                "server_id": server_id,
                "agent_id": agent_id,
                "status_code": "APPROVED",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception("Agent enrollment failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "code": "ENROLL_FAILED",
                "message": f"에이전트 등록 중 오류가 발생했습니다: {str(e)}"
            }
        )


# ──────────────────────────────────────────────
# POST /heartbeat  - Agent 하트비트 수신 (인증 필요)
# ──────────────────────────────────────────────

@router.post("/heartbeat", response_model=HeartbeatResponse)
def receive_heartbeat(
    req: HeartbeatRequest,
    agent: Agent = Depends(verify_agent),
    db: Session = Depends(get_db),
):
    """
    승인된 Agent의 하트비트를 수신합니다.
    - mon_agent_heartbeat_hist에 이력 INSERT
    - mon_agent_status_curr의 현재 상태 UPSERT
    - mon_agent.last_connected_at 갱신
    """
    now = datetime.now(timezone.utc)

    try:
        # 1) 하트비트 이력 저장
        hb = AgentHeartbeatHist(
            agent_id=agent.agent_id,
            server_id=agent.server_id,
            delay_ms=0,  # Agent가 보내는 지연값이 없으면 0
            local_queue_count=req.local_queue_count or 0,
            collected_at=now,
            received_at=now,
        )
        db.add(hb)

        # 2) Agent 현재 상태 갱신 (UPSERT)
        existing_status = db.get(AgentStatusCurr, agent.agent_id)
        if existing_status:
            existing_status.agent_status = 'NORMAL'
            existing_status.delay_ms = 0
            existing_status.local_queue_count = req.local_queue_count or 0
            existing_status.last_heartbeat_at = now
        else:
            new_status = AgentStatusCurr(
                agent_id=agent.agent_id,
                agent_status='NORMAL',
                delay_ms=0,
                local_queue_count=req.local_queue_count or 0,
                last_heartbeat_at=now,
            )
            db.add(new_status)

        # 3) mon_agent.last_connected_at 갱신
        agent.last_connected_at = now
        if req.agent_version:
            agent.agent_version = req.agent_version
        agent.updated_at = now

        db.commit()
        config = build_agent_config(agent, db)

        return HeartbeatResponse(
            success=True,
            code="OK",
            data=config.model_dump(),
            message="하트비트가 정상적으로 수신되었습니다."
        )

    except Exception as e:
        db.rollback()
        logger.exception("Heartbeat processing failed for agent_id=%d: %s", agent.agent_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "code": "HEARTBEAT_FAILED",
                "message": f"하트비트 처리 중 오류가 발생했습니다: {str(e)}"
            }
        )


# ──────────────────────────────────────────────
# POST /metrics/bulk  - 지표 Bulk 수신 (인증 필요)
# ──────────────────────────────────────────────

@router.post("/metrics/bulk", response_model=MetricBulkResponse)
def receive_metrics(
    req: MetricBulkRequest,
    agent: Agent = Depends(verify_agent),
    db: Session = Depends(get_db),
):
    """
    승인된 Agent로부터 지표 데이터를 Bulk로 수신합니다.
    - mon_metric_curr에 최신값 UPSERT
    - mon_metric_hist에 이력 INSERT
    """
    now = datetime.now(timezone.utc)
    received_count = 0
    
    # 배치 내 중복 제거 (같은 collected_at 시점의 메트릭은 하나만 유지)
    try:
        seen = {}
        for item in req.items:
            key = (item.metric_code, item.dimension_key or "-", item.dimension_value or "-")
            previous = seen.get(key)
            if previous is None or item.collected_at >= previous.collected_at:
                seen[key] = item
        unique_items = list(seen.values())
        
        if len(unique_items) < len(req.items):
            logger.warning(
                "Removed %d duplicate metrics from batch (total: %d -> %d)",
                len(req.items) - len(unique_items), len(req.items), len(unique_items)
            )
            req.items = unique_items
    except Exception as e:
        logger.warning("Deduplication failed: %s, continuing with all items", str(e))

    try:
        next_result_id = None
        if any(item.metric_code in CHECK_RESULT_METRICS for item in req.items):
            ensure_check_result_hist_table(db)
            next_result_id = next_check_result_id(db)

        replace_codes = {item.metric_code for item in req.items if item.metric_code in REPLACE_SET_METRICS}
        for metric_code in replace_codes:
            ensure_metric_def(db, metric_code)
            db.execute(
                delete(MetricCurrent).where(
                    MetricCurrent.server_id == agent.server_id,
                    MetricCurrent.metric_code == metric_code,
                )
            )

        for item in req.items:
            dim_key = item.dimension_key or "-"
            dim_value = item.dimension_value or "-"
            ensure_metric_def(db, item.metric_code)

            # 1) mon_metric_curr UPSERT (복합 PK: server_id + metric_code + dim_key + dim_value)
            existing = db.execute(
                select(MetricCurrent).where(
                    MetricCurrent.server_id == agent.server_id,
                    MetricCurrent.metric_code == item.metric_code,
                    MetricCurrent.dimension_key == dim_key,
                    MetricCurrent.dimension_value == dim_value,
                )
            ).scalar_one_or_none()

            if existing:
                existing.metric_value = item.metric_value
                existing.string_value = item.string_value
                existing.status_code = item.status_code
                existing.collected_at = item.collected_at
                existing.received_at = now
            else:
                new_curr = MetricCurrent(
                    server_id=agent.server_id,
                    metric_code=item.metric_code,
                    dimension_key=dim_key,
                    dimension_value=dim_value,
                    metric_value=item.metric_value,
                    string_value=item.string_value,
                    status_code=item.status_code,
                    collected_at=item.collected_at,
                    received_at=now,
                )
                db.add(new_curr)

            # 2) mon_metric_hist INSERT
            hist = MetricHistory(
                server_id=agent.server_id,
                agent_id=agent.agent_id,
                metric_code=item.metric_code,
                dimension_key=dim_key,
                dimension_value=dim_value,
                metric_value=item.metric_value,
                string_value=item.string_value,
                status_code=item.status_code,
                quality_code=item.quality_code,
                collected_at=item.collected_at,
                received_at=now,
                batch_uid=req.batch_uid,
            )
            # History partition maintenance is separate from live metric display.
            # ORA-14400 on mon_metric_hist must not roll back mon_metric_curr.
            # TODO: re-enable after creating the required history partitions.
            # db.add(hist)
            if item.metric_code in CHECK_RESULT_METRICS:
                db.add(CheckResultHistory(
                    check_result_id=next_result_id,
                    server_id=agent.server_id,
                    agent_id=agent.agent_id,
                    target_type_code=CHECK_RESULT_METRICS[item.metric_code],
                    target_name=dim_value,
                    metric_code=item.metric_code,
                    metric_value=item.metric_value,
                    string_value=item.string_value,
                    status_code=item.status_code,
                    collected_at=item.collected_at,
                    received_at=now,
                ))
                next_result_id += 1
            received_count += 1

        # Agent 마지막 접속 시각 갱신
        agent.last_connected_at = now
        agent.updated_at = now

        db.commit()

        logger.info(
            "Metrics received: agent_id=%d, batch_uid=%s, count=%d",
            agent.agent_id, req.batch_uid, received_count
        )

        return MetricBulkResponse(
            success=True,
            code="OK",
            message=f"지표 {received_count}건이 정상적으로 수신되었습니다.",
            received_count=received_count,
        )

    except Exception as e:
        db.rollback()
        logger.exception("Metrics processing failed for agent_id=%d: %s", agent.agent_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "code": "METRICS_FAILED",
                "message": f"지표 처리 중 오류가 발생했습니다: {str(e)}"
            }
        )


# ──────────────────────────────────────────────
# GET /config  - Agent 수집 설정 조회 (인증 필요)
# ──────────────────────────────────────────────

@router.get("/config", response_model=AgentConfigResponse)
def get_agent_config(
    agent: Agent = Depends(verify_agent),
    db: Session = Depends(get_db),
):
    """
    승인된 Agent에게 수집 설정을 내려보냅니다.
    향후 서버별/그룹별 개별 설정을 지원할 수 있도록 구조를 잡아둡니다.
    """
    # TODO: 서버별/그룹별 설정을 DB에서 조회하도록 확장
    config = build_agent_config(agent, db)

    return AgentConfigResponse(
        success=True,
        code="OK",
        data=config,
    )
