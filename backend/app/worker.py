import time
import logging
import uuid
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select, and_

from app.core.database import SessionLocal
from app.models.event import EventRule, Event
from app.models.resource import MetricCurrent

logger = logging.getLogger(__name__)

def evaluate_condition(val: float, op: str, threshold: float) -> bool:
    if threshold is None: return False
    if op == '>': return val > threshold
    if op == '>=': return val >= threshold
    if op == '<': return val < threshold
    if op == '<=': return val <= threshold
    if op == '==': return val == threshold
    if op == '!=': return val != threshold
    return False

def check_thresholds():
    """
    주기적으로 mon_metric_curr 데이터를 스캔하여
    mon_event_rule에 정의된 임계치를 벗어난 경우 이벤트를 발생시킵니다.
    """
    db = SessionLocal()
    try:
        # 1. 활성화된 룰 조회
        rules = db.execute(select(EventRule).where(EventRule.use_yn == 'Y')).scalars().all()
        if not rules:
            return
            
        rule_map = {}
        for r in rules:
            rule_map.setdefault(r.target_metric, []).append(r)
            
        now = datetime.now(timezone.utc)
        
        # 2. 모든 현재 메트릭 조회
        metrics = db.execute(select(MetricCurrent)).scalars().all()
        
        for metric in metrics:
            target_rules = rule_map.get(metric.metric_code, [])
            for rule in target_rules:
                val = metric.metric_value
                if val is None:
                    continue
                    
                # 심각도 판정 (Fatal -> Crit -> Warn 순으로 체크)
                triggered_severity = None
                
                if evaluate_condition(val, rule.compare_op, rule.fatal_threshold):
                    triggered_severity = 'FATAL'
                elif evaluate_condition(val, rule.compare_op, rule.crit_threshold):
                    triggered_severity = 'CRITICAL'
                elif evaluate_condition(val, rule.compare_op, rule.warn_threshold):
                    triggered_severity = 'WARNING'
                    
                # 기존 OPEN 상태인 이벤트 조회
                stmt = select(Event).where(
                    and_(
                        Event.rule_id == rule.rule_id,
                        Event.server_id == metric.server_id,
                        Event.target_key == metric.dimension_value,
                        Event.status_code == 'OPEN'
                    )
                )
                existing_event = db.execute(stmt).scalar_one_or_none()
                
                if triggered_severity:
                    if existing_event:
                        # 이미 이벤트가 있고 심각도가 다르면 갱신
                        existing_event.last_occurred_at = now
                        existing_event.occurrence_count = (existing_event.occurrence_count or 1) + 1
                        if existing_event.severity_code != triggered_severity:
                            existing_event.severity_code = triggered_severity
                            existing_event.message = f"{metric.metric_code} 값이 {val}입니다. ({triggered_severity} 상향)"
                    else:
                        # 신규 이벤트 발생
                        new_event = Event(
                            event_uid=str(uuid.uuid4()),
                            rule_id=rule.rule_id,
                            server_id=metric.server_id,
                            target_type_code="SERVER",
                            target_key=metric.dimension_value,
                            severity_code=triggered_severity,
                            status_code="OPEN",
                            title=f"[{triggered_severity}] {rule.rule_name} 발생",
                            message=f"{metric.metric_code} 값이 {val}입니다.",
                            first_occurred_at=now,
                            last_occurred_at=now,
                            occurrence_count=1
                        )
                        db.add(new_event)
                        logger.warning(f"New Event Created: {new_event.title} (Server: {metric.server_id})")
                else:
                    # 정상 범위인 경우 (Recover 판단)
                    if existing_event:
                        # recover_threshold 판단 로직 (단순화: 지정되지 않았다면 바로 복구)
                        is_recovered = False
                        if rule.recover_threshold is not None:
                            # 역방향 연산자 적용
                            rev_op = '<' if '>' in rule.compare_op else '>'
                            if evaluate_condition(val, rev_op, rule.recover_threshold):
                                is_recovered = True
                        else:
                            is_recovered = True
                            
                        if is_recovered:
                            existing_event.status_code = 'CLOSED'
                            existing_event.recovered_at = now
                            existing_event.message += f" | 정상 수치({val})로 복구되었습니다."
                            logger.info(f"Event Closed: {existing_event.title} (Server: {metric.server_id})")
                            
        db.commit()
    except Exception as e:
        logger.error(f"Error in check_thresholds: {e}")
        db.rollback()
    finally:
        db.close()

def start_worker():
    scheduler = BackgroundScheduler()
    # 30초마다 임계치 검사 수행
    scheduler.add_job(check_thresholds, 'interval', seconds=30, id='threshold_worker')
    scheduler.start()
    logger.info("Threshold Worker started.")
    return scheduler

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s - %(message)s')
    start_worker()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Worker stopped.")
