import pytest
from datetime import datetime, timezone
from app.domain.check_targets import normalize_names, normalize_ports, check_targets_to_dict

class MockCheckTarget:
    def __init__(self, target_type_code, target_name, use_yn="Y"):
        self.check_target_id = 1
        self.server_id = 100
        self.target_type_code = target_type_code
        self.target_name = target_name
        self.use_yn = use_yn
        self.created_at = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
        self.updated_at = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)

def test_normalize_names():
    assert normalize_names([" nginx ", "NGINX", "", "apache", "  "]) == ["nginx", "apache"]
    assert normalize_names([]) == []
    assert normalize_names(None) == []
    assert normalize_names(["a", "A", "b"]) == ["a", "b"]

def test_normalize_ports():
    assert normalize_ports([80, 8080, "80", 0, -1, 65536, "abc"]) == ["80", "8080"]
    assert normalize_ports([]) == []
    assert normalize_ports(None) == []

def test_check_targets_to_dict():
    items = [
        MockCheckTarget("PROCESS", "nginx"),
        MockCheckTarget("SERVICE", "docker"),
        MockCheckTarget("PORT", "80"),
        MockCheckTarget("PORT", "invalid_port"),
    ]
    res = check_targets_to_dict(items)
    assert res["processes"] == ["nginx"]
    assert res["services"] == ["docker"]
    assert res["ports"] == [80]
    
    assert "items" in res
    assert len(res["items"]) == 4
    
    first_item = res["items"][0]
    assert first_item["target_type_code"] == "PROCESS"
    assert first_item["target_name"] == "nginx"
    assert first_item["created_at"] == "2026-09-16T12:00:00+00:00"
