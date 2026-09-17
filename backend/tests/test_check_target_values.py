from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.check_targets import normalize_names, normalize_ports, check_targets_to_dict
from datetime import datetime

class DummyCheckTarget:
    def __init__(self, target_type_code, target_name):
        self.check_target_id = 1
        self.server_id = 1
        self.target_type_code = target_type_code
        self.target_name = target_name
        self.use_yn = "Y"
        self.created_at = datetime(2023, 1, 1)
        self.updated_at = datetime(2023, 1, 1)

def test_normalize_names():
    assert normalize_names([" a ", "B", "A", "", None]) == ["a", "B", "None"]

def test_normalize_ports():
    assert normalize_ports([80, 80, 0, 65536, "443", "abc", None]) == ["80", "443"]

def test_check_targets_to_dict():
    items = [
        DummyCheckTarget("PROCESS", "python"),
        DummyCheckTarget("SERVICE", "nginx"),
        DummyCheckTarget("PORT", "80"),
    ]
    res = check_targets_to_dict(items)
    assert res["processes"] == ["python"]
    assert res["services"] == ["nginx"]
    assert res["ports"] == [80]
    assert len(res["items"]) == 3
