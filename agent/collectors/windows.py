from typing import List, Dict, Any
from .base import BaseCollector

class WindowsServiceCollector(BaseCollector):
    """
    Windows 환경 전용 수집기 (스텁)
    차후 pywin32 등을 이용하여 Windows 서비스 상태 등을 수집합니다.
    """
    def collect(self) -> List[Dict[str, Any]]:
        # TODO: Implement Windows specific metrics collection
        return []
