from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, CHAR, TIMESTAMP
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime, timezone

class ExternalHealthCheck(Base):
    """P3: URL/SSL, log, database, batch/file health check adapter/mock"""
    __tablename__ = "ext_health_check"

    id = Column(Integer, primary_key=True, autoincrement=True)
    target_type = Column(String(30), nullable=False) # URL, SSL, LOG, DB, BATCH, FILE
    target_url_or_path = Column(String(500), nullable=False)
    status = Column(String(30), nullable=False) # PASS, FAIL, UNKNOWN
    mock_response = Column(Text)
    checked_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))

class RemoteCommandApproval(Base):
    """P3: Remote command allowlisted command registry and approval state"""
    __tablename__ = "ext_remote_cmd_approval"

    id = Column(Integer, primary_key=True, autoincrement=True)
    command_type = Column(String(100), nullable=False) # MUST BE ALLOWLISTED
    target_server = Column(String(100), nullable=False)
    approval_state = Column(String(30), nullable=False) # PENDING, APPROVED, REJECTED
    dry_run_result = Column(Text)
    audit_event = Column(Text)
    requested_by = Column(String(100))
    requested_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))

class ConfigVersion(Base):
    """P3: Config versioning, rollback metadata, report/retention"""
    __tablename__ = "ext_config_version"

    id = Column(Integer, primary_key=True, autoincrement=True)
    component_name = Column(String(100), nullable=False)
    version_tag = Column(String(50), nullable=False)
    config_payload = Column(Text)
    rollback_metadata = Column(Text)
    created_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))

class HAClusterState(Base):
    """P3: HA/failover health/readiness state, leader/follower simulation"""
    __tablename__ = "ext_ha_cluster_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    node_name = Column(String(100), nullable=False, unique=True)
    role = Column(String(30), nullable=False) # LEADER, FOLLOWER
    health_state = Column(String(30), nullable=False) # HEALTHY, UNHEALTHY
    last_heartbeat = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))
