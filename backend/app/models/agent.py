from sqlalchemy import Column, String, Integer, ForeignKey, CHAR, TIMESTAMP
from sqlalchemy.orm import relationship
from app.core.database import Base


class Agent(Base):
    """mon_agent - 에이전트(수집 데몬) 정보"""
    __tablename__ = "mon_agent"

    agent_id = Column(Integer, primary_key=True)
    agent_uid = Column(String(40), nullable=False, unique=True)
    server_id = Column(Integer, ForeignKey("mon_server.server_id"), nullable=False)
    agent_version = Column(String(50))
    install_path = Column(String(500))
    run_account = Column(String(100))
    status_code = Column(String(30), nullable=False, default='PENDING')
    started_at = Column(TIMESTAMP)
    last_connected_at = Column(TIMESTAMP)
    auto_update_yn = Column(CHAR(1), default='N')
    created_at = Column(TIMESTAMP)
    updated_at = Column(TIMESTAMP)

    server = relationship("Server", back_populates="agent")
    status_curr = relationship("AgentStatusCurr", back_populates="agent", uselist=False)


class AgentHeartbeatHist(Base):
    """mon_agent_heartbeat_hist - 에이전트 하트비트 이력"""
    __tablename__ = "mon_agent_heartbeat_hist"

    heartbeat_id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, nullable=False)         # FK 제약조건 DB에 없음
    server_id = Column(Integer, nullable=False)         # FK 제약조건 DB에 없음
    delay_ms = Column(Integer)
    local_queue_count = Column(Integer)
    collected_at = Column(TIMESTAMP, nullable=False)
    received_at = Column(TIMESTAMP, nullable=False)


class AgentStatusCurr(Base):
    """mon_agent_status_curr - 에이전트 현재 상태"""
    __tablename__ = "mon_agent_status_curr"

    agent_id = Column(Integer, ForeignKey("mon_agent.agent_id"), primary_key=True)
    agent_status = Column(String(30), nullable=False)
    delay_ms = Column(Integer)
    local_queue_count = Column(Integer)
    last_heartbeat_at = Column(TIMESTAMP)

    agent = relationship("Agent", back_populates="status_curr")
