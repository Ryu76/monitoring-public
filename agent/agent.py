import logging
import os
import sys
import time
import uuid
from datetime import datetime

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings
from spool import MetricSpooler
from collectors.common import SystemResourceCollector


class MonitorAgent:
    def __init__(self):
        self.spooler = MetricSpooler(settings.SPOOL_DB_PATH)
        self.collectors = [SystemResourceCollector()]
        self.agent_uid = None
        self.server_uid = None
        self.headers = {"Content-Type": "application/json"}
        self._load_uid()

    def _load_uid(self):
        if os.path.exists(settings.AGENT_UID_FILE):
            with open(settings.AGENT_UID_FILE, "r") as f:
                self.agent_uid = f.read().strip()
        if os.path.exists(settings.SERVER_UID_FILE):
            with open(settings.SERVER_UID_FILE, "r") as f:
                self.server_uid = f.read().strip()

        if self.agent_uid:
            self.headers["X-Agent-Uid"] = self.agent_uid
            logger.info("Loaded existing agent UID: %s", self.agent_uid)

    def enroll(self) -> bool:
        url = f"{settings.API_BASE_URL}/enroll"
        payload = {
            "host_name": settings.HOST_NAME,
            "os_type_code": settings.OS_TYPE_CODE,
            "os_name": settings.OS_NAME,
            "os_version": settings.OS_VERSION,
            "mgmt_ip": settings.MGMT_IP,
            "service_ip": settings.SERVICE_IP,
            "agent_version": settings.AGENT_VERSION,
            "install_path": settings.INSTALL_PATH,
            "run_account": settings.RUN_ACCOUNT,
        }

        try:
            logger.info("Attempting to enroll agent to %s...", url)
            resp = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            if resp.status_code != 201:
                logger.error("Enrollment failed: %s - %s", resp.status_code, resp.text)
                return False

            data = resp.json().get("data", {})
            self.agent_uid = data.get("agent_uid")
            self.server_uid = data.get("server_uid")

            with open(settings.AGENT_UID_FILE, "w") as f:
                f.write(self.agent_uid)
            with open(settings.SERVER_UID_FILE, "w") as f:
                f.write(self.server_uid)

            self.headers["X-Agent-Uid"] = self.agent_uid
            logger.info("Enrollment successful. Agent UID: %s", self.agent_uid)
            return True
        except Exception as e:
            logger.error("Enrollment connection error: %s", e)
            return False

    def apply_config(self, data: dict):
        settings.COLLECT_INTERVAL_SEC = int(data.get("collect_interval_sec") or settings.COLLECT_INTERVAL_SEC)
        settings.HEARTBEAT_INTERVAL_SEC = int(data.get("heartbeat_interval_sec") or settings.HEARTBEAT_INTERVAL_SEC)
        settings.METRICS_BATCH_SIZE = int(data.get("metrics_batch_size") or settings.METRICS_BATCH_SIZE)
        settings.CHECK_PROCESSES = ",".join(data.get("check_processes") or [])
        settings.CHECK_SERVICES = ",".join(data.get("check_services") or [])
        settings.CHECK_PORTS = ",".join(str(port) for port in (data.get("check_ports") or []))
        logger.info(
            "Backend check request applied: processes=%s services=%s ports=%s",
            settings.CHECK_PROCESSES or "-",
            settings.CHECK_SERVICES or "-",
            settings.CHECK_PORTS or "-",
        )

    def send_heartbeat(self):
        if not self.agent_uid:
            return

        url = f"{settings.API_BASE_URL}/heartbeat"
        payload = {
            "local_queue_count": self.spooler.get_count(),
            "agent_version": settings.AGENT_VERSION,
        }
        try:
            resp = requests.post(url, json=payload, headers=self.headers, timeout=5)
            if resp.status_code == 200:
                config = resp.json().get("data", {})
                if config:
                    self.apply_config(config)
                logger.debug("Heartbeat sent successfully.")
            else:
                logger.warning("Heartbeat failed: %s - %s", resp.status_code, resp.text)
        except Exception as e:
            logger.error("Heartbeat connection error: %s", e)

    def refresh_config(self):
        if not self.agent_uid:
            return

        url = f"{settings.API_BASE_URL}/config"
        try:
            resp = requests.get(url, headers=self.headers, timeout=5)
            if resp.status_code != 200:
                logger.warning("Config fetch failed: %s - %s", resp.status_code, resp.text)
                return
            self.apply_config(resp.json().get("data", {}))
        except Exception as e:
            logger.error("Config fetch error: %s", e)

    def collect_and_spool(self):
        all_metrics = []
        for collector in self.collectors:
            try:
                all_metrics.extend(collector.collect())
            except Exception as e:
                logger.error("Collector %s failed: %s", collector.__class__.__name__, e)

        if all_metrics:
            self.spooler.push(all_metrics)
            logger.debug("Collected and spooled %d metrics.", len(all_metrics))

    def flush_spool(self):
        if not self.agent_uid:
            return

        if self.spooler.get_count() == 0:
            return

        url = f"{settings.API_BASE_URL}/metrics/bulk"
        sequence = 0

        while True:
            batch = self.spooler.pop_batch(settings.METRICS_BATCH_SIZE)
            if not batch:
                break

            payload = {
                "batch_uid": str(uuid.uuid4()),
                "sequence": sequence,
                "collected_at": datetime.utcnow().isoformat() + "Z",
                "items": batch,
            }
            sequence += 1

            try:
                resp = requests.post(url, json=payload, headers=self.headers, timeout=10)
                if resp.status_code == 200:
                    logger.info("Successfully flushed %d metrics to server.", len(batch))
                else:
                    logger.warning("Failed to flush metrics: %s - %s", resp.status_code, resp.text)
                    self.spooler.push(batch)
                    break
            except Exception as e:
                logger.error("Flush connection error: %s", e)
                self.spooler.push(batch)
                break

    def run(self):
        logger.info("Starting Monitor Agent...")

        while not self.agent_uid:
            if not self.enroll():
                logger.info("Retrying enrollment in 10 seconds...")
                time.sleep(10)

        last_collect_time = 0
        last_heartbeat_time = 0

        while True:
            current_time = time.time()

            if current_time - last_heartbeat_time >= settings.HEARTBEAT_INTERVAL_SEC:
                self.send_heartbeat()
                last_heartbeat_time = current_time

            if current_time - last_collect_time >= settings.COLLECT_INTERVAL_SEC:
                self.collect_and_spool()
                self.flush_spool()
                last_collect_time = current_time

            time.sleep(1)


if __name__ == "__main__":
    agent = MonitorAgent()
    try:
        agent.run()
    except KeyboardInterrupt:
        logger.info("Agent stopped by user.")
