import pytest
import os
os.environ["DB_USER"] = "test"
os.environ["DB_PASSWORD"] = "test"
os.environ["DB_HOST"] = "localhost"
os.environ["DB_PORT"] = "1521"
os.environ["DB_SERVICE_NAME"] = "TEST"
os.environ["SECRET_KEY"] = "test"

from sqlalchemy.orm import Session
from datetime import datetime, timezone
import json

from app.core.audit import log_audit
from app.models.system import SysAuditLog
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_log_audit_transaction(db_session: Session):
    # Test that log_audit does not commit the transaction prematurely
    # and handles auto-increment correctly
    
    before_count = db_session.query(SysAuditLog).count()
    
    # Start a transaction logically
    log_audit(
        db=db_session,
        user_id=1,
        action_type="TEST",
        target_entity="TestEntity",
        target_id="123",
        before_data={"test": "before"},
        after_data={"test": "after"},
        ip_address="127.0.0.1"
    )
    
    # At this point, it shouldn't be visible to other sessions because it's not committed
    other_session = TestingSessionLocal()
    other_count = other_session.query(SysAuditLog).count()
    other_session.close()
    
    assert other_count == before_count, "log_audit committed prematurely!"
    
    # Now commit
    db_session.commit()
    
    # Now it should be visible
    other_session = TestingSessionLocal()
    other_count_after = other_session.query(SysAuditLog).count()
    other_session.close()
    
    assert other_count_after == before_count + 1
    
    # Fetch the newly added log
    log = db_session.query(SysAuditLog).filter_by(action_type="TEST").first()
    assert log is not None
    assert log.target_entity == "TestEntity"
    assert log.log_id is not None
