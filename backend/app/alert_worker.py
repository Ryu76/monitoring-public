import time
import logging
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select, and_

from app.core.database import SessionLocal
from app.models.event import Event, AlertPolicy, AlertOutbox, AlertHistory
from app.core.notifier import Notifier

logger = logging.getLogger(__name__)

MAX_RETRY = 3

def process_alerts():
    """
    이벤트 중 아직 알림이 발송되지 않은 건들에 대해 알림 정책(mon_alert_policy)을 평가하고
    Outbox에 등록한 뒤, Outbox의 PENDING/FAILED 건들을 처리합니다. (ALT-001)
    """
    db = SessionLocal()
    try:
        # Step 1: Enqueue (Event -> AlertOutbox)
        stmt = select(Event).where(
            and_(
                Event.status_code == 'OPEN',
                Event.message.notlike('%[ENQUEUED]%')
            )
        )
        unnotified_events = db.execute(stmt).scalars().all()

        policies = db.execute(select(AlertPolicy).where(AlertPolicy.is_active == 1)).scalars().all()
        policy_map = {p.severity_level: p for p in policies}

        target_map = {
            'EMAIL': 'admin@nexusmon.local',
            'SMS': '010-0000-0000',
            'SLACK': 'http://mock-slack-url.local/webhook',
            'TEST': 'test-target'
        }

        for evt in unnotified_events:
            policy = policy_map.get(evt.severity_code)
            if policy:
                target = target_map.get(policy.notify_channel, 'admin')
                outbox_entry = AlertOutbox(
                    event_uid=evt.event_uid,
                    policy_id=policy.policy_id,
                    target=target,
                    title=evt.title,
                    message=evt.message,
                    status='PENDING',
                    retry_count=0,
                    created_at=datetime.now(timezone.utc)
                )
                db.add(outbox_entry)
                evt.message = f"{evt.message} [ENQUEUED]"

        db.commit()

        # Step 2: Process Outbox
        outbox_stmt = select(AlertOutbox).where(
            AlertOutbox.status.in_(['PENDING', 'FAILED'])
        )
        pending_outbox = db.execute(outbox_stmt).scalars().all()

        for outbox in pending_outbox:
            if outbox.status == 'FAILED' and outbox.retry_count >= MAX_RETRY:
                # MAX_RETRY 초과 시 FAILED 로 History 기록 후 Outbox에서 삭제
                history = AlertHistory(
                    event_uid=outbox.event_uid,
                    policy_id=outbox.policy_id,
                    target=outbox.target,
                    title=outbox.title,
                    message=outbox.message,
                    status='FAILED',
                    error_msg='Max retry exceeded',
                    sent_at=datetime.now(timezone.utc)
                )
                db.add(history)
                db.delete(outbox)
                continue

            outbox.status = 'PROCESSING'
            db.commit()

            try:
                policy = db.execute(select(AlertPolicy).where(AlertPolicy.policy_id == outbox.policy_id)).scalars().first()
                if policy:
                    Notifier.dispatch(
                        channel=policy.notify_channel,
                        target=outbox.target,
                        title=outbox.title,
                        message=outbox.message
                    )

                # Success
                history = AlertHistory(
                    event_uid=outbox.event_uid,
                    policy_id=outbox.policy_id,
                    target=outbox.target,
                    title=outbox.title,
                    message=outbox.message,
                    status='SUCCESS',
                    error_msg='',
                    sent_at=datetime.now(timezone.utc)
                )
                db.add(history)
                db.delete(outbox)
            except Exception as e:
                # Failure
                outbox.status = 'FAILED'
                outbox.retry_count += 1
                if outbox.retry_count >= MAX_RETRY:
                    history = AlertHistory(
                        event_uid=outbox.event_uid,
                        policy_id=outbox.policy_id,
                        target=outbox.target,
                        title=outbox.title,
                        message=outbox.message,
                        status='FAILED',
                        error_msg=str(e),
                        sent_at=datetime.now(timezone.utc)
                    )
                    db.add(history)
                    db.delete(outbox)

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
