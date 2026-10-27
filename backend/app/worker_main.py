import logging
import time
import os
import sys
import signal

from app.worker import start_worker
from app.scheduler import start_scheduler
from app.alert_worker import start_alert_worker
from app.aggregator import start_aggregator

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s - %(message)s')
logger = logging.getLogger(__name__)

schedulers = []
lock_fd = None
LOCK_FILE = "worker_local.lock"

def acquire_local_lock():
    global lock_fd
    try:
        if os.name == 'nt':
            import msvcrt
            lock_fd = os.open(LOCK_FILE, os.O_CREAT | os.O_RDWR)
            try:
                msvcrt.locking(lock_fd, msvcrt.LK_NBLCK, 1)
                return True
            except OSError:
                os.close(lock_fd)
                lock_fd = None
                return False
        else:
            import fcntl
            lock_fd = os.open(LOCK_FILE, os.O_CREAT | os.O_RDWR)
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except OSError:
                os.close(lock_fd)
                lock_fd = None
                return False
    except Exception as e:
        logger.error(f"Error acquiring lock: {e}")
        return False

def release_local_lock():
    global lock_fd
    if lock_fd is not None:
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock_fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
        except Exception as e:
            logger.error(f"Error releasing lock: {e}")
        finally:
            lock_fd = None
            try:
                os.remove(LOCK_FILE)
            except OSError:
                pass

running = True

def handle_shutdown(signum, frame):
    global running
    logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
    running = False

def main():
    if not acquire_local_lock():
        logger.error("Another worker instance is already running locally (local lock acquired). Exiting to prevent duplicate scheduled work.")
        logger.warning("Note: This relies on a local lock. Do not claim HA coordination as true DB/distributed lock is not implemented.")
        sys.exit(1)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    if os.name == 'nt':
        try:
            signal.signal(signal.SIGBREAK, handle_shutdown)
        except AttributeError:
            pass

    logger.info("Starting background workers (schema is managed by Alembic)...")
    try:
        schedulers.append(start_worker())
        schedulers.append(start_scheduler())
        schedulers.append(start_alert_worker())
        schedulers.append(start_aggregator())
        
        logger.info("All background workers started. Press Ctrl+C to stop.")
        
        while running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received.")
    finally:
        logger.info("Shutting down background workers gracefully (bounded cleanup)...")
        for s in schedulers:
            if s and s.running:
                s.shutdown(wait=True)
        logger.info("All background workers shut down.")
        release_local_lock()

if __name__ == "__main__":
    main()
