from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Table, CHAR, TIMESTAMP
from sqlalchemy.orm import relationship
from app.core.database import Base


class Server(Base):
    """mon_server - 서버 자산 정보"""
    __tablename__ = "mon_server"

    server_id = Column(Integer, primary_key=True)
    server_uid = Column(String(40), nullable=False, unique=True)
    server_name = Column(String(100), nullable=False)
    host_name = Column(String(255))
    mgmt_ip = Column(String(45))
    service_ip = Column(String(45))
    os_type_code = Column(String(30))   # 공통코드: OS_TYPE (WINDOWS, LINUX, AIX ...)
    os_name = Column(String(100))
    os_version = Column(String(100))
    server_role_code = Column(String(30))  # 공통코드: SERVER_ROLE (WEB, WAS, DB ...)
    env_code = Column(String(30))          # 공통코드: ENV (PROD, DEV, STG ...)
    importance_code = Column(String(30))   # 공통코드: IMPORTANCE (HIGH, MEDIUM, LOW)
    owner_dept = Column(String(100))
    owner_name = Column(String(100))
    use_yn = Column(CHAR(1), nullable=False, default='Y')
    created_at = Column(TIMESTAMP)
    created_by = Column(String(100))
    updated_at = Column(TIMESTAMP)
    updated_by = Column(String(100))

    # Relationships
    agent = relationship("Agent", back_populates="server", uselist=False)
    status_curr = relationship("ServerStatusCurr", back_populates="server", uselist=False)


class ServerStatusCurr(Base):
    """mon_server_status_curr - 서버 종합 상태 현황"""
    __tablename__ = "mon_server_status_curr"

    server_id = Column(Integer, ForeignKey("mon_server.server_id"), primary_key=True)
    composite_status = Column(String(30), nullable=False)  # NORMAL, WARNING, CRITICAL, UNKNOWN
    reason_msg = Column(String(500))
    last_updated_at = Column(TIMESTAMP)

    server = relationship("Server", back_populates="status_curr")
