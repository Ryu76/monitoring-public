from sqlalchemy import Column, String, Integer, ForeignKey, Text, CHAR, TIMESTAMP, Date
from app.core.database import Base


class EventRule(Base):
    """mon_event_rule - 이벤트 발생 규칙 정의"""
    __tablename__ = "mon_event_rule"

    rule_id = Column(Integer, primary_key=True)
    rule_name = Column(String(200), nullable=False)
    target_metric = Column(String(60))
    compare_op = Column(String(10))
    warn_threshold = Column(Integer)         # Oracle NUMBER
    crit_threshold = Column(Integer)         # Oracle NUMBER
    fatal_threshold = Column(Integer)        # Oracle NUMBER
    duration_sec = Column(Integer)
    continuous_count = Column(Integer)
    recover_threshold = Column(Integer)      # Oracle NUMBER
    recover_duration_sec = Column(Integer)
    severity_code = Column(String(30))
    use_yn = Column(CHAR(1), nullable=False, default='Y')  # Oracle CHAR(1)
    created_at = Column(TIMESTAMP)
    updated_at = Column(TIMESTAMP)


class Event(Base):
    """mon_event - 이벤트(장애) 발생 이력"""
    __tablename__ = "mon_event"

    event_id = Column(Integer)
    event_uid = Column(String(40), nullable=False, unique=True)
    rule_id = Column(Integer)              # FK 제약조건 DB에 없음
    server_id = Column(Integer)            # FK 제약조건 DB에 없음
    target_type_code = Column(String(30))
    target_key = Column(String(200))
    severity_code = Column(String(30), nullable=False)
    status_code = Column(String(30), nullable=False)
    title = Column(String(500), nullable=False)
    message = Column(String(2000))
    first_occurred_at = Column(TIMESTAMP, nullable=False)
    last_occurred_at = Column(TIMESTAMP)
    recovered_at = Column(TIMESTAMP)
    occurrence_count = Column(Integer, default=1)
    ack_user_id = Column(Integer)
    ack_at = Column(TIMESTAMP)
    incident_id = Column(Integer)          # FK 제약조건 DB에 없음

    __mapper_args__ = {
        "primary_key": [event_uid]
    }


class AlertPolicy(Base):
    """mon_alert_policy - 알림 정책"""
    __tablename__ = "mon_alert_policy"

    policy_id = Column(String(50), primary_key=True)
    policy_name = Column(String(100), nullable=False)
    severity_level = Column(String(20))
    notify_channel = Column(String(50))
    is_active = Column(Integer)
    created_at = Column(Date)              # Oracle DATE

class AlertOutbox(Base):
    """mon_alert_outbox - 발송 대기열 (ALT-001)"""
    __tablename__ = "mon_alert_outbox"

    outbox_id = Column(Integer, primary_key=True)
    event_uid = Column(String(40), nullable=False)
    policy_id = Column(String(50), nullable=False)
    target = Column(String(200), nullable=False)
    title = Column(String(500), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(30), default='PENDING') # PENDING, PROCESSING
    retry_count = Column(Integer, default=0)
    created_at = Column(TIMESTAMP, nullable=False)

class AlertHistory(Base):
    """mon_alert_hist - 발송 이력 (ALT-001)"""
    __tablename__ = "mon_alert_hist"

    history_id = Column(Integer, primary_key=True)
    event_uid = Column(String(40))
    policy_id = Column(String(50))
    target = Column(String(200))
    title = Column(String(500))
    message = Column(Text)
    status = Column(String(30)) # SUCCESS, FAILED
    error_msg = Column(Text)
    sent_at = Column(TIMESTAMP, nullable=False)


class Incident(Base):
    """mon_incident - 장애 인시던트"""
    __tablename__ = "mon_incident"

    incident_id = Column(Integer, primary_key=True)
    incident_title = Column(String(500), nullable=False)
    status_code = Column(String(30), nullable=False)
    impact_code = Column(String(30))
    cause_code = Column(String(30))
    assigned_to = Column(Integer)
    detected_at = Column(TIMESTAMP)
    resolved_at = Column(TIMESTAMP)
    closed_at = Column(TIMESTAMP)
    created_by = Column(String(100))
    updated_at = Column(TIMESTAMP)


class IncidentAction(Base):
    """mon_incident_action - 장애 조치 내역"""
    __tablename__ = "mon_incident_action"

    action_id = Column(Integer, primary_key=True)
    incident_id = Column(Integer, nullable=False)   # FK 제약조건 DB에 없음
    action_user_id = Column(Integer)
    action_note = Column(Text)           # Oracle CLOB
    action_at = Column(TIMESTAMP)


class LogEntry(Base):
    """mon_log_entry - 로그 수집 데이터"""
    __tablename__ = "mon_log_entry"

    # DB에서 log_entry_id는 nullable이며 PK가 아님
    log_entry_id = Column(Integer)
    server_id = Column(Integer, nullable=False)     # FK 제약조건 DB에 없음
    log_source_id = Column(Integer)
    log_level = Column(String(30))
    log_message = Column(Text)           # Oracle CLOB
    trace_id = Column(String(100))
    logged_at = Column(TIMESTAMP, nullable=False)
    received_at = Column(TIMESTAMP)

    __mapper_args__ = {
        "primary_key": [log_entry_id]
    }
