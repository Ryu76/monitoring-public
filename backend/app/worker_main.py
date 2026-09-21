import logging
import time
from app.worker import start_worker
from app.scheduler import start_scheduler
from app.alert_worker import start_alert_worker
from app.aggregator import start_aggregator


logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting background workers (schema is managed by Alembic)...")
    start_worker()
    start_scheduler()
    start_alert_worker()
    start_aggregator()

    logger.info("All background workers started. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down background workers.")

if __name__ == "__main__":
    main()
