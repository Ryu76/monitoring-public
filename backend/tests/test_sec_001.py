import pytest
import os
import sys
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os
os.environ["DB_USER"] = "test-user"
os.environ["DB_PASSWORD"] = "test-pass"
os.environ["DB_HOST"] = "localhost"
os.environ["DB_PORT"] = "1521"
os.environ["DB_SERVICE_NAME"] = "TEST"
os.environ["SECRET_KEY"] = "super-secret-key-for-tests"

from app.main import app
from app.core.database import Base
from app.api.dependencies import get_db
from app.models.system import SysUser, SysRole, SysUserRole, SysPermission, SysCode, SysAuditLog
from app.models.server import Server, ServerStatusCurr
from app.models.agent import Agent, AgentStatusCurr
from app.models.event import Event, Incident, IncidentAction
from app.models.resource import MetricCurrent
from app.models.process import CheckTarget, CheckResultHistory
import jwt
from app.core.config import settings

# Test DB in file
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


class SEC001Tests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        
        # Add test users to DB
        db = TestingSessionLocal()
        # Admin user
        admin = SysUser(user_id=1, login_id="admin_test", user_name="Admin", password_hash="hash", status_code="ACTIVE", use_yn="Y")
        viewer = SysUser(user_id=2, login_id="viewer_test", user_name="Viewer", password_hash="hash", status_code="ACTIVE", use_yn="Y")
        db.add_all([admin, viewer])
        
        # Roles
        admin_role = SysRole(role_id=1, role_code="ADMIN", role_name="Admin")
        viewer_role = SysRole(role_id=2, role_code="VIEWER", role_name="Viewer")
        db.add_all([admin_role, viewer_role])
        
        db.commit()
        
        # User roles
        ur1 = SysUserRole(user_id=1, role_id=1)
        ur2 = SysUserRole(user_id=2, role_id=2)
        db.add_all([ur1, ur2])
        db.commit()
        db.close()
        
        self.admin_token = jwt.encode({"sub": "admin_test"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        self.viewer_token = jwt.encode({"sub": "viewer_test"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    def tearDown(self):
        db = TestingSessionLocal()
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
        db.close()

    def test_no_token_returns_401(self):
        response = self.client.get("/api/v1/dashboard/summary")
        self.assertEqual(response.status_code, 401)

    def test_viewer_can_read_dashboard(self):
        response = self.client.get(
            "/api/v1/dashboard/summary",
            headers={"Authorization": f"Bearer {self.viewer_token}"}
        )
        self.assertEqual(response.status_code, 200)

    def test_viewer_cannot_update_server(self):
        response = self.client.put(
            "/api/v1/servers/1",
            json={"server_name": "New Name"},
            headers={"Authorization": f"Bearer {self.viewer_token}"}
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_update_server(self):
        db = TestingSessionLocal()
        from app.models.server import Server
        server = Server(server_id=1, server_uid="srv-1", server_name="Old Name", host_name="h1", os_type_code="LNX")
        db.add(server)
        db.commit()
        db.close()

        response = self.client.put(
            "/api/v1/servers/1",
            json={"server_name": "New Name"},
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(response.status_code, 200)
        
        # Check audit log
        db = TestingSessionLocal()
        audit_log = db.execute(select(SysAuditLog).where(SysAuditLog.target_entity == "Server")).scalar_one_or_none()
        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.action_type, "UPDATE")
        self.assertEqual(audit_log.user_id, 1)
        self.assertIn("Old Name", audit_log.before_data)
        self.assertIn("New Name", audit_log.after_data)
        db.close()

if __name__ == "__main__":
    unittest.main()

@pytest.fixture(autouse=True)
def setup_overrides():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
