import time
import logging
import uuid
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select, and_

from app.core.database import SessionLocal
from app.models.agent import AgentStatusCurr, Agent
from app.models.event import Event

logger = logging.getLogger(__name__)

def check_agent_offline():
    """
    최종 하트비트 시각이 2분을 초과한 에이전트를 감지하여
    오프라인(장애) 이벤트를 발생시킵니다.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        threshold_time = now - timedelta(minutes=2)
        
        # 1. 하트비트 시각이 2분 경과한 상태 조회
        stmt = select(AgentStatusCurr).where(AgentStatusCurr.last_heartbeat_at < threshold_time)
        offline_agents = db.execute(stmt).scalars().all()
        
        for status in offline_agents:
            if status.agent_status != 'OFFLINE':
                # 상태 업데이트
                status.agent_status = 'OFFLINE'
                
                # 에이전트 정보 획득
                agent = db.execute(select(Agent).where(Agent.agent_id == status.agent_id)).scalar_one_or_none()
                server_id = agent.server_id if agent else None
                
                # 중복 이벤트가 없는지 확인
                evt_stmt = select(Event).where(
                    and_(
                        Event.server_id == server_id,
                        Event.target_type_code == 'AGENT',
                        Event.title == '[FATAL] 에이전트 연결 끊김',
                        Event.status_code == 'OPEN'
                    )
                )
                existing_evt = db.execute(evt_stmt).scalar_one_or_none()
                
                if not existing_evt:
                    new_evt = Event(
                        event_uid=str(uuid.uuid4()),
                        server_id=server_id,
                        target_type_code='AGENT',
                        target_key=str(status.agent_id),
                        severity_code='FATAL',
                        status_code='OPEN',
                        title='[FATAL] 에이전트 연결 끊김',
                        message='에이전트로부터 2분 이상 하트비트가 수신되지 않았습니다.',
                        first_occurred_at=now,
                        last_occurred_at=now,
                        occurrence_count=1
                    )
                    db.add(new_evt)
                    logger.warning(f"Agent Offline Event Created for Agent ID: {status.agent_id}")
                    
        # 2. 반대로 복구된 에이전트(OFFLINE이었으나 하트비트가 최근 갱신된 경우) 이벤트 닫기
        open_evts = db.execute(select(Event).where(
            and_(
                Event.target_type_code == 'AGENT',
                Event.title == '[FATAL] 에이전트 연결 끊김',
                Event.status_code == 'OPEN'
            )
        )).scalars().all()
        
        for evt in open_evts:
            agent_id = int(evt.target_key) if evt.target_key and evt.target_key.isdigit() else None
            if agent_id:
                curr_status = db.execute(select(AgentStatusCurr).where(AgentStatusCurr.agent_id == agent_id)).scalar_one_or_none()
                # 현재 상태가 NORMAL 이면 장애 복구 처리
                if curr_status and curr_status.agent_status == 'NORMAL':
                    evt.status_code = 'CLOSED'
                    evt.recovered_at = now
                    evt.message += " | 에이전트 연결이 정상 복구되었습니다."
                    logger.info(f"Agent Offline Event Closed for Agent ID: {agent_id}")

        db.commit()
    except Exception as e:
        logger.error(f"Error in check_agent_offline: {e}")
        db.rollback()
    finally:
        db.close()

def start_scheduler():
    scheduler = BackgroundScheduler()
    # 1분마다 미수신 에이전트 검사 수행
    scheduler.add_job(check_agent_offline, 'interval', minutes=1, id='agent_offline_checker')
    scheduler.start()
    logger.info("Agent Offline Scheduler started.")
    return scheduler

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s - %(message)s')
    start_scheduler()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped.")
