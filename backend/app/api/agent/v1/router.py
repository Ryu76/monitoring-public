"""Agent API v1 라우터 - 등록, 하트비트, 지표 수신, 설정 조회"""

import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, delete, update
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import get_db, verify_agent
from app.core.query_batches import oracle_in_chunks
from app.models.server import Server, ServerStatusCurr
from app.models.agent import Agent, AgentHeartbeatHist, AgentStatusCurr
from app.models.resource import (
    CheckSnapshotWatermark,
    MetricCurrent,
    MetricHistory,
    MetricDef,
    MetricReceiptLedger,
)
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
    "CPU_CORE_PCT": ("CPU Core Usage (%)", "CPU", "FLOAT", "PERCENT", "AVG"),
    "CPU_LOAD_1M": ("CPU Load 1M", "CPU", "FLOAT", "COUNT", "AVG"),
    "CPU_LOAD_5M": ("CPU Load 5M", "CPU", "FLOAT", "COUNT", "AVG"),
    "CPU_LOAD_15M": ("CPU Load 15M", "CPU", "FLOAT", "COUNT", "AVG"),
    "MEM_USAGE_PCT": ("Memory Usage (%)", "MEMORY", "FLOAT", "PERCENT", "AVG"),
    "MEM_AVAILABLE_BYTES": ("Memory Available (Bytes)", "MEMORY", "BIGINT", "BYTES", "AVG"),
    "SWAP_USAGE_PCT": ("Swap Usage (%)", "MEMORY", "FLOAT", "PERCENT", "AVG"),
    "SWAP_AVAILABLE_BYTES": ("Swap Available (Bytes)", "MEMORY", "BIGINT", "BYTES", "AVG"),
    "DISK_USAGE_PCT": ("Disk Usage (%)", "DISK", "FLOAT", "PERCENT", "AVG"),
    "DISK_AVAILABLE_BYTES": ("Disk Available (Bytes)", "DISK", "BIGINT", "BYTES", "AVG"),
    "DISK_IO_READ_BYTES": ("Disk IO Read Bytes", "DISK", "BIGINT", "BYTES", "SUM"),
    "DISK_IO_WRITE_BYTES": ("Disk IO Write Bytes", "DISK", "BIGINT", "BYTES", "SUM"),
    "DISK_IO_READ_TIME": ("Disk IO Read Time", "DISK", "FLOAT", "MILLISECONDS", "SUM"),
    "DISK_IO_WRITE_TIME": ("Disk IO Write Time", "DISK", "FLOAT", "MILLISECONDS", "SUM"),
    "NET_BYTES_SENT": ("Network Bytes Sent", "NETWORK", "BIGINT", "BYTES", "SUM"),
    "NET_BYTES_RECV": ("Network Bytes Received", "NETWORK", "BIGINT", "BYTES", "SUM"),
    "NET_BYTES_SENT_RATE": ("Network Bytes Sent Rate", "NETWORK", "BIGINT", "BYTES", "SUM"),
    "NET_BYTES_RECV_RATE": ("Network Bytes Received Rate", "NETWORK", "BIGINT", "BYTES", "SUM"),
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


def ensure_metric_defs(db: Session, metric_codes: set[str]) -> None:
    """Create missing definitions with one preload query, not one SELECT per item."""
    if not metric_codes:
        return

    existing_codes: set[str] = set()
    for metric_code_chunk in oracle_in_chunks(metric_codes):
        existing_codes.update(
            db.execute(
                select(MetricDef.metric_code).where(
                    MetricDef.metric_code.in_(metric_code_chunk)
                )
            ).scalars()
        )
    missing_codes = metric_codes - existing_codes
    if not missing_codes:
        return

    created_at = datetime.now(timezone.utc)
    db.add_all([
        MetricDef(
            metric_code=metric_code,
            metric_name=METRIC_DEFINITIONS.get(
                metric_code, (metric_code, "CUSTOM", "FLOAT", "COUNT", "LAST")
            )[0],
            category_code=METRIC_DEFINITIONS.get(
                metric_code, (metric_code, "CUSTOM", "FLOAT", "COUNT", "LAST")
            )[1],
            value_type_code=METRIC_DEFINITIONS.get(
                metric_code, (metric_code, "CUSTOM", "FLOAT", "COUNT", "LAST")
            )[2],
            unit_code=METRIC_DEFINITIONS.get(
                metric_code, (metric_code, "CUSTOM", "FLOAT", "COUNT", "LAST")
            )[3],
            agg_type_code=METRIC_DEFINITIONS.get(
                metric_code, (metric_code, "CUSTOM", "FLOAT", "COUNT", "LAST")
            )[4],
            windows_support_yn="Y",
            linux_support_yn="Y",
            use_yn="Y",
            created_at=created_at,
        )
        for metric_code in missing_codes
    ])
    # MetricCurrent and CheckSnapshotWatermark carry MetricDef foreign keys.
    db.flush()


def acquire_replace_set_snapshot(
    db: Session,
    *,
    server_id: int,
    metric_code: str,
    collected_at: datetime,
    received_at: datetime,
) -> bool:
    """Atomically acquire the right to replace one metric's current set.

    The conditional UPDATE is the normal compare-and-set path. On Oracle it
    obtains the row's write lock and reevaluates the timestamp predicate after
    a competing writer commits; SQLite also evaluates the predicate atomically
    within its writer transaction. A missing row is initialized in a savepoint
    so a primary-key collision rolls back only that INSERT, not the enclosing
    ingestion transaction.
    """
    conditional_advance = (
        update(CheckSnapshotWatermark)
        .where(
            CheckSnapshotWatermark.server_id == server_id,
            CheckSnapshotWatermark.metric_code == metric_code,
            CheckSnapshotWatermark.collected_at <= collected_at,
        )
        .values(collected_at=collected_at, received_at=received_at)
    )

    while True:
        # Never delete current rows until this compare-and-set has succeeded.
        # A conditional UPDATE is also row-locking on databases that support
        # row-level locks.
        if db.execute(conditional_advance).rowcount == 1:
            return True

        # A zero rowcount means either a newer row exists or the row is absent.
        # Lock an existing row before deciding it is stale, so it cannot advance
        # between that decision and the later delete.
        watermark = db.execute(
            select(CheckSnapshotWatermark)
            .where(
                CheckSnapshotWatermark.server_id == server_id,
                CheckSnapshotWatermark.metric_code == metric_code,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if watermark is not None:
            if collected_at < watermark.collected_at:
                return False

            # Fallback for drivers without a reliable UPDATE rowcount. The row
            # remains locked through the enclosing transaction, so replacement
            # is still serialized with concurrent snapshots.
            watermark.collected_at = collected_at
            watermark.received_at = received_at
            return True

        try:
            # The row was absent when checked. Another transaction can still
            # initialize it first, so isolate the unique-key failure in a
            # savepoint and retry the conditional acquisition in that case.
            with db.begin_nested():
                db.add(CheckSnapshotWatermark(
                    server_id=server_id,
                    metric_code=metric_code,
                    collected_at=collected_at,
                    received_at=received_at,
                ))
                db.flush()
            return True
        except IntegrityError:
            continue


def build_agent_config(agent: Agent, db: Session) -> AgentConfigData:
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


    existing_ledger = db.execute(
        select(MetricReceiptLedger).where(MetricReceiptLedger.batch_uid == req.batch_uid)
    ).scalar_one_or_none()

    if existing_ledger:
        return MetricBulkResponse(
            success=True,
            code="OK",
            message=f"배치({req.batch_uid})가 이미 처리되었습니다.",
            received_count=existing_ledger.item_count,
        )

    # 배치 내 중복 제거 (같은 collected_at 시점의 메트릭은 하나만 유지)
    try:
        seen = {}
        for item in req.items:
            key = (item.metric_code, item.dimension_key or "-", item.dimension_value or "-", item.collected_at)
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
        metric_codes = {item.metric_code for item in req.items}
        ensure_metric_defs(db, metric_codes)

        # PROCESS/SERVICE/PORT values are snapshots, not independent current
        # observations. A durable per-metric watermark must be checked before
        # delete-and-replace so a delayed spool replay cannot erase new rows.
        stale_replace_codes: set[str] = set()
        replace_codes = {
            item.metric_code for item in req.items
            if item.metric_code in REPLACE_SET_METRICS
        }
        snapshot_at_by_code = {
            metric_code: max(
                item.collected_at for item in req.items if item.metric_code == metric_code
            )
            for metric_code in replace_codes
        }
        for metric_code in replace_codes:
            snapshot_at = snapshot_at_by_code[metric_code]
            if not acquire_replace_set_snapshot(
                db,
                server_id=agent.server_id,
                metric_code=metric_code,
                collected_at=snapshot_at,
                received_at=now,
            ):
                stale_replace_codes.add(metric_code)
                logger.info(
                    "Rejecting stale %s snapshot for server_id=%d at %s",
                    metric_code,
                    agent.server_id,
                    snapshot_at,
                )
                continue

            db.execute(
                delete(MetricCurrent).where(
                    MetricCurrent.server_id == agent.server_id,
                    MetricCurrent.metric_code == metric_code,
                )
            )

        accepted_items = [
            item for item in req.items
            if item.metric_code not in stale_replace_codes
        ]
        accepted_codes = {item.metric_code for item in accepted_items}
        # Preload current rows once for every metric family in this request.
        # The map also retains unflushed rows created later in this batch.
        current_rows: list[MetricCurrent] = []
        for metric_code_chunk in oracle_in_chunks(accepted_codes):
            current_rows.extend(
                db.execute(
                    select(MetricCurrent).where(
                        MetricCurrent.server_id == agent.server_id,
                        MetricCurrent.metric_code.in_(metric_code_chunk),
                    )
                ).scalars()
            )
        current_by_key: dict[tuple[int, str, str, str], MetricCurrent] = {
            (
                current.server_id,
                current.metric_code,
                current.dimension_key,
                current.dimension_value,
            ): current
            for current in current_rows
        }

        for item in accepted_items:
            dim_key = item.dimension_key or "-"
            dim_value = item.dimension_value or "-"
            current_key = (agent.server_id, item.metric_code, dim_key, dim_value)

            # mon_metric_curr UPSERT (composite PK: server/code/dimension).
            existing = current_by_key.get(current_key)
            if existing:
                if item.collected_at >= existing.collected_at:
                    existing.metric_value = item.metric_value
                    existing.string_value = item.string_value
                    existing.status_code = item.status_code
                    existing.collected_at = item.collected_at
                    existing.received_at = now
                else:
                    # ING-002: 과거 metric이 current 역전 안 함
                    pass
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
                current_by_key[current_key] = new_curr

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
            db.add(hist)

            if item.metric_code in CHECK_RESULT_METRICS:
                db.add(CheckResultHistory(
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
            received_count += 1

        # Make history/check-result insertion fail before an ACK is even added.
        # Commit below is one transaction, so receipt, watermark, current, and
        # history state either persist together or are all rolled back.
        db.flush()
        db.add(MetricReceiptLedger(
            batch_uid=req.batch_uid,
            agent_id=agent.agent_id,
            received_at=now,
            item_count=received_count
        ))

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
