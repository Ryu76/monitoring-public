import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.models.system import SysAuditLog
from fastapi import Request

def get_client_ip(request: Request) -> str:
    if request.client:
        return request.client.host
    return "unknown"

def log_audit(db: Session, user_id: int, action_type: str, target_entity: str, target_id: str, before_data: dict, after_data: dict, ip_address: str):
    log_id_query = db.execute(select(func.max(SysAuditLog.log_id))).scalar()
    log_id = (log_id_query or 0) + 1
    audit_log = SysAuditLog(
        log_id=log_id,
        user_id=user_id,
        action_type=action_type,
        target_entity=target_entity,
        target_id=target_id,
        ip_address=ip_address,
        before_data=json.dumps(before_data) if before_data else None,
        after_data=json.dumps(after_data) if after_data else None,
        created_at=datetime.now(timezone.utc)
    )
    db.add(audit_log)
    db.commit()
