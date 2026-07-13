import time
import logging
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select, and_

from app.core.database import SessionLocal
from app.models.event import Event, AlertPolicy

logger = logging.getLogger(__name__)

def process_alerts():
    """
    이벤트 중 아직 알림이 발송되지 않은 건들에 대해 알림 정책(mon_alert_policy)을 평가하고
    알림을 발송(콘솔 로그 출력)합니다.
    """
    db = SessionLocal()
    try:
        stmt = select(Event).where(
            and_(
                Event.status_code == 'OPEN',
                Event.message.notlike('%[ALERT_SENT]%')
            )
        )
        unnotified_events = db.execute(stmt).scalars().all()
        
        policies = db.execute(select(AlertPolicy).where(AlertPolicy.is_active == 1)).scalars().all()
        policy_map = {p.severity_level: p for p in policies}
        
        for evt in unnotified_events:
            policy = policy_map.get(evt.severity_code)
            if policy:
                from app.core.notifier import Notifier
                # 실제 운영 환경에서는 시스템 설정이나 사용자 정보를 조회하여 대상을 결정합니다.
                target_map = {
                    'EMAIL': 'admin@nexusmon.local',
                    'SMS': '010-0000-0000',
                    'SLACK': '' # Webhook URL
                }
                target = target_map.get(policy.notify_channel, 'admin')
                
                Notifier.dispatch(
                    channel=policy.notify_channel,
                    target=target,
                    title=evt.title,
                    message=evt.message
                )
                evt.message = f"{evt.message} [ALERT_SENT]"
                
        db.commit()
    except Exception as e:
        logger.error(f"Error processing alerts: {e}")
        db.rollback()
    finally:
        db.close()

def start_alert_worker():
    scheduler = BackgroundScheduler()
    scheduler.add_job(process_alerts, 'interval', seconds=30, id='alert_worker')
    scheduler.start()
    logger.info("Alert Worker started.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s - %(message)s')
    start_alert_worker()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Alert Worker stopped.")
