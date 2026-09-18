from sqlalchemy import Column, Integer, String, CHAR, TIMESTAMP
from app.core.database import Base


class CheckTarget(Base):
    """Server-specific process, service, and port check targets."""
    __tablename__ = "mon_check_target"

    check_target_id = Column(Integer, primary_key=True)
    server_id = Column(Integer, nullable=False)
    target_type_code = Column(String(30), nullable=False)
    target_name = Column(String(200), nullable=False)
    use_yn = Column(CHAR(1), nullable=False, default="Y")
    created_at = Column(TIMESTAMP)
    updated_at = Column(TIMESTAMP)


class CheckResultHistory(Base):
    """Historical process, service, and port check results sent by agents."""
    __tablename__ = "mon_check_result_hist"

    check_result_id = Column(Integer, primary_key=True)
    server_id = Column(Integer, nullable=False)
    agent_id = Column(Integer)
    target_type_code = Column(String(30), nullable=False)
    target_name = Column(String(200), nullable=False)
    metric_code = Column(String(60), nullable=False)
    metric_value = Column(Integer)
    string_value = Column(String(1000))
    status_code = Column(String(30))
    collected_at = Column(TIMESTAMP, nullable=False)
    received_at = Column(TIMESTAMP, nullable=False)
# 현재는 import 호환성을 위해 파일만 유지합니다.
