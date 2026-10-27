import pytest
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional

from app.domain.check_targets import normalize_names, normalize_ports, check_targets_to_dict


@dataclass
class MockCheckTarget:
    check_target_id: int
    server_id: int
    target_type_code: str
    target_name: str
    use_yn: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


def test_normalize_names():
    # 대소문자 중복, 공백, 빈 값
    names = ["  nginx ", "Nginx", "redis", "", "  ", None]
    result = normalize_names(names)
    assert result == ["nginx", "redis", "None"]


def test_normalize_ports():
    # 유효/무효 포트, 중복, 문자열
    ports = [80, "80", 65536, 0, -1, 443, "abc", None]
    result = normalize_ports(ports)
    assert result == ["80", "443"]


def test_check_targets_to_dict():
    now = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
    items = [
        MockCheckTarget(1, 100, "PROCESS", "nginx", "Y", now, now),
        MockCheckTarget(2, 100, "SERVICE", "ssh", "Y", now, now),
        MockCheckTarget(3, 100, "PORT", "80", "Y", now, now),
    ]
    
    result = check_targets_to_dict(items)
    
    assert "processes" in result
    assert "services" in result
    assert "ports" in result
    assert "items" in result
    
    assert result["processes"] == ["nginx"]
    assert result["services"] == ["ssh"]
    assert result["ports"] == [80]
    
    assert len(result["items"]) == 3
    assert result["items"][0]["check_target_id"] == 1
    assert result["items"][0]["created_at"] == now.isoformat()
