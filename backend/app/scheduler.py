import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.query_batches import oracle_in_chunks
from app.models.agent import Agent, AgentStatusCurr
from app.models.event import Event

logger = logging.getLogger(__name__)
OFFLINE_EVENT_TITLE = "[FATAL] 에이전트 연결 끊김"


def check_agent_offline():
    """Batch-load agents, open events, and statuses for the scheduler cycle."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        threshold_time = now - timedelta(minutes=2)
        offline_rows = db.execute(
            select(AgentStatusCurr, Agent.server_id)
            .outerjoin(Agent, Agent.agent_id == AgentStatusCurr.agent_id)
            .where(AgentStatusCurr.last_heartbeat_at < threshold_time)
        ).all()
        open_events = db.execute(
            select(Event).where(
                Event.target_type_code == "AGENT",
                Event.title == OFFLINE_EVENT_TITLE,
                Event.status_code == "OPEN",
            )
        ).scalars().all()
        open_event_by_server = {event.server_id: event for event in open_events}

        for current_status, server_id in offline_rows:
            if current_status.agent_status == "OFFLINE":
                continue
            current_status.agent_status = "OFFLINE"
            if server_id in open_event_by_server:
                continue

            new_event = Event(
                event_uid=str(uuid.uuid4()),
                server_id=server_id,
                target_type_code="AGENT",
                target_key=str(current_status.agent_id),
                severity_code="FATAL",
                status_code="OPEN",
                title=OFFLINE_EVENT_TITLE,
                message="에이전트로부터 2분 이상 하트비트가 수신되지 않았습니다.",
                first_occurred_at=now,
                last_occurred_at=now,
                occurrence_count=1,
            )
            db.add(new_event)
            open_events.append(new_event)
            open_event_by_server[server_id] = new_event
            logger.warning("Agent Offline Event Created for Agent ID: %s", current_status.agent_id)

        event_agent_ids = {
            int(event.target_key)
            for event in open_events
            if event.target_key and event.target_key.isdigit()
        }
        statuses_by_agent_id: dict[int, AgentStatusCurr] = {}
        for agent_id_chunk in oracle_in_chunks(event_agent_ids):
            statuses_by_agent_id.update({
                status.agent_id: status
                for status in db.execute(
                    select(AgentStatusCurr).where(
                        AgentStatusCurr.agent_id.in_(agent_id_chunk)
                    )
                ).scalars()
            })

        for event in open_events:
            agent_id = int(event.target_key) if event.target_key and event.target_key.isdigit() else None
            current_status = statuses_by_agent_id.get(agent_id) if agent_id is not None else None
            if current_status and current_status.agent_status == "NORMAL":
                event.status_code = "CLOSED"
                event.recovered_at = now
                event.message += " | 에이전트 연결이 정상 복구되었습니다."
                logger.info("Agent Offline Event Closed for Agent ID: %s", agent_id)

        db.commit()
    except Exception as exc:
        logger.error("Error in check_agent_offline: %s", exc)
        db.rollback()
    finally:
        db.close()


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_agent_offline, "interval", minutes=1, id="agent_offline_checker")
    scheduler.start()
    logger.info("Agent Offline Scheduler started.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    start_scheduler()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped.")
