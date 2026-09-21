import json
from datetime import datetime, timezone
from typing import List, Dict, Any
from .base import BaseCollector

class MockExternalHealthCollector(BaseCollector):
    """
    P3: URL/SSL, log, database, batch/file collector의 development-safe health inspection interface.
    Mock/Adapter를 사용하여 실제 외부 연동 없이 Normalized Result Model 생성
    """
    def __init__(self):
        super().__init__()
        self.targets = [
            {"type": "URL", "path": "https://example.com/api", "simulated_status": "PASS"},
            {"type": "SSL", "path": "example.com:443", "simulated_status": "PASS"},
            {"type": "LOG", "path": "/var/log/syslog", "simulated_status": "WARN"},
            {"type": "DB", "path": "jdbc:mysql://localhost:3306/test", "simulated_status": "PASS"},
            {"type": "BATCH", "path": "daily_batch_job", "simulated_status": "FAIL"},
            {"type": "FILE", "path": "/data/exports/data.csv", "simulated_status": "PASS"},
        ]

    def collect(self) -> List[Dict[str, Any]]:
        metrics = []
        collected_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        for target in self.targets:
            # Normalized Result Model
            val = 1.0 if target["simulated_status"] == "PASS" else 0.0
            metrics.append({
                "metric_code": f"EXT_HEALTH_{target['type']}",
                "dimension_key": "target",
                "dimension_value": target["path"],
                "metric_value": val,
                "string_value": json.dumps({"status": target["simulated_status"], "mock": True}),
                "status_code": "OK" if target["simulated_status"] == "PASS" else ("WARN" if target["simulated_status"] == "WARN" else "CRITICAL"),
                "quality_code": "GOOD",
                "collected_at": collected_at,
            })

        return metrics
