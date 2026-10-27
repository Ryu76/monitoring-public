import logging
import time
import uuid
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.query_batches import oracle_in_chunks
from app.models.event import Event, EventRule
from app.models.resource import MetricCurrent

logger = logging.getLogger(__name__)


def evaluate_condition(val: float, op: str, threshold: float) -> bool:
    if threshold is None:
        return False
    if op == ">":
        return val > threshold
    if op == ">=":
        return val >= threshold
    if op == "<":
        return val < threshold
    if op == "<=":
        return val <= threshold
    if op == "==":
        return val == threshold
    if op == "!=":
        return val != threshold
    return False


def check_thresholds():
    """Evaluate active rules without issuing one OPEN-event query per metric."""
    db = SessionLocal()
    try:
        rules = db.execute(
            select(EventRule).where(EventRule.use_yn == "Y")
        ).scalars().all()
        if not rules:
            return

        rule_map: dict[str, list[EventRule]] = {}
        for rule in rules:
            rule_map.setdefault(rule.target_metric, []).append(rule)

        metrics = db.execute(select(MetricCurrent)).scalars().all()
        open_events: list[Event] = []
        for rule_id_chunk in oracle_in_chunks([rule.rule_id for rule in rules]):
            open_events.extend(
                db.execute(
                    select(Event).where(
                        Event.status_code == "OPEN",
                        Event.rule_id.in_(rule_id_chunk),
                    )
                ).scalars()
            )
        events_by_key = {
            (event.rule_id, event.server_id, event.target_key): event
            for event in open_events
        }
        now = datetime.now(timezone.utc)

        for metric in metrics:
            for rule in rule_map.get(metric.metric_code, []):
                if metric.metric_value is None:
                    continue

                event_key = (rule.rule_id, metric.server_id, metric.dimension_value)
                existing_event = events_by_key.get(event_key)
                triggered_severity = None
                if evaluate_condition(metric.metric_value, rule.compare_op, rule.fatal_threshold):
                    triggered_severity = "FATAL"
                elif evaluate_condition(metric.metric_value, rule.compare_op, rule.crit_threshold):
                    triggered_severity = "CRITICAL"
                elif evaluate_condition(metric.metric_value, rule.compare_op, rule.warn_threshold):
                    triggered_severity = "WARNING"

                if triggered_severity:
                    if existing_event:
                        existing_event.last_occurred_at = now
                        existing_event.occurrence_count = (existing_event.occurrence_count or 1) + 1
                        if existing_event.severity_code != triggered_severity:
                            existing_event.severity_code = triggered_severity
                            existing_event.message = (
                                f"{metric.metric_code} 값이 {metric.metric_value}입니다. "
                                f"({triggered_severity} 상향)"
                            )
                    else:
                        new_event = Event(
                            event_uid=str(uuid.uuid4()),
                            rule_id=rule.rule_id,
                            server_id=metric.server_id,
                            target_type_code="SERVER",
                            target_key=metric.dimension_value,
                            severity_code=triggered_severity,
                            status_code="OPEN",
                            title=f"[{triggered_severity}] {rule.rule_name} 발생",
                            message=f"{metric.metric_code} 값이 {metric.metric_value}입니다.",
                            first_occurred_at=now,
                            last_occurred_at=now,
                            occurrence_count=1,
                        )
                        db.add(new_event)
                        events_by_key[event_key] = new_event
                        logger.warning(
                            "New Event Created: %s (Server: %s)",
                            new_event.title,
                            metric.server_id,
                        )
                elif existing_event:
                    is_recovered = (
                        evaluate_condition(
                            metric.metric_value,
                            "<" if ">" in rule.compare_op else ">",
                            rule.recover_threshold,
                        )
                        if rule.recover_threshold is not None
                        else True
                    )
                    if is_recovered:
                        existing_event.status_code = "CLOSED"
                        existing_event.recovered_at = now
                        existing_event.message += f" | 정상 수치({metric.metric_value})로 복구되었습니다."
                        events_by_key.pop(event_key, None)
                        logger.info(
                            "Event Closed: %s (Server: %s)",
                            existing_event.title,
                            metric.server_id,
                        )

        db.commit()
    except Exception as exc:
        logger.error("Error in check_thresholds: %s", exc)
        db.rollback()
    finally:
        db.close()


def start_worker():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_thresholds, "interval", seconds=30, id="threshold_worker")
    scheduler.start()
    logger.info("Threshold Worker started.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    start_worker()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Worker stopped.")
