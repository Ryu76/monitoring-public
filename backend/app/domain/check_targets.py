from typing import List, Any

def normalize_names(values: List[str]) -> List[str]:
    result = []
    seen = set()
    for value in values or []:
        normalized = str(value).strip()
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result

def normalize_ports(values: List[int]) -> List[str]:
    result = []
    seen = set()
    for value in values or []:
        try:
            port = int(value)
        except (TypeError, ValueError):
            continue
        if 1 <= port <= 65535 and port not in seen:
            seen.add(port)
            result.append(str(port))
    return result

def check_targets_to_dict(items: List[Any]):
    processes = [i.target_name for i in items if i.target_type_code == "PROCESS"]
    services = [i.target_name for i in items if i.target_type_code == "SERVICE"]
    ports = [int(i.target_name) for i in items if i.target_type_code == "PORT" and str(i.target_name).isdigit()]
    return {
        "processes": processes,
        "services": services,
        "ports": ports,
        "items": [
            {
                "check_target_id": i.check_target_id,
                "server_id": i.server_id,
                "target_type_code": i.target_type_code,
                "target_name": i.target_name,
                "use_yn": i.use_yn,
                "created_at": i.created_at.isoformat() if i.created_at else None,
                "updated_at": i.updated_at.isoformat() if i.updated_at else None,
            }
            for i in items
        ],
    }
