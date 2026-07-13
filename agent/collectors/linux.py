from typing import List, Dict, Any
from .base import BaseCollector

class LinuxSystemdCollector(BaseCollector):
    """
    Linux 환경 전용 수집기 (스텁)
    차후 systemd 서비스 상태 및 특화 지표를 수집합니다.
    """
    def collect(self) -> List[Dict[str, Any]]:
        # TODO: Implement Linux specific metrics collection
        return []
