from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseCollector(ABC):
    """모든 수집기가 상속받아야 하는 기본 클래스"""
    
    @abstractmethod
    def collect(self) -> List[Dict[str, Any]]:
        """
        수집된 지표의 리스트를 반환합니다.
        각 dict는 다음의 구조를 가져야 합니다:
        {
            "metric_code": str,
            "dimension_key": str,
            "dimension_value": str,
            "metric_value": float,
            "string_value": str,
            "status_code": str,
            "quality_code": str,
            "collected_at": str (ISO format UTC)
        }
        """
        pass
