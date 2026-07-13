import functools
import json
import logging
from datetime import datetime, timezone
import asyncio

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.system import SysAuditLog

logger = logging.getLogger(__name__)

def audit_log(action_type: str, target_entity: str):
    """
    주요 CUD 작업 후 SYS_AUDIT_LOG에 이력을 남기는 데코레이터
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 기존 함수 실행
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # 후처리 감사 로깅
            try:
                current_user = kwargs.get('current_user')
                user_id = current_user.user_id if current_user else None
                
                db = SessionLocal()
                try:
                    log_entry = SysAuditLog(
                        user_id=user_id,
                        action_type=action_type,
                        target_entity=target_entity,
                        target_id=None,
                        ip_address=None,
                        before_data=None, 
                        after_data=json.dumps({"result": "success"}),
                        created_at=datetime.now(timezone.utc)
                    )
                    db.add(log_entry)
                    db.commit()
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"Audit log writing failed: {e}")
                
            return result
        return wrapper
    return decorator
