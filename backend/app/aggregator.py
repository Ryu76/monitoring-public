import time
import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.resource import MetricCurrent, MetricHistory

logger = logging.getLogger(__name__)

def aggregate_metrics_5m():
    """
    일정 시간 지난 MetricCurrent 데이터를 MetricHistory로 아카이빙하는 시계열 집계기
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(minutes=5)
        
        stmt = select(MetricCurrent).where(MetricCurrent.updated_at < start_time)
        old_metrics = db.execute(stmt).scalars().all()
        
        for m in old_metrics:
            hist = MetricHistory(
                server_id=m.server_id,
                metric_code=m.metric_code,
                dimension_value=m.dimension_value,
                collected_at=m.updated_at,
                metric_value=m.metric_value
            )
            db.add(hist)
            db.delete(m)
            
        db.commit()
        if old_metrics:
            logger.info(f"Aggregated {len(old_metrics)} metrics to history.")
    except Exception as e:
        logger.error(f"Error in aggregation: {e}")
        db.rollback()
    finally:
        db.close()

def start_aggregator():
    scheduler = BackgroundScheduler()
    scheduler.add_job(aggregate_metrics_5m, 'interval', minutes=5, id='aggregator_5m')
    scheduler.start()
    logger.info("Metric Aggregator started.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s - %(message)s')
    start_aggregator()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Aggregator stopped.")
