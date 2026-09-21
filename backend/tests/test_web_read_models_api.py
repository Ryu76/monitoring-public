import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
import jwt

os.environ.setdefault("DB_USER", "test-user")
os.environ.setdefault("DB_PASSWORD", "test-password")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "1521")
os.environ.setdefault("DB_SERVICE_NAME", "test-service")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.dependencies import get_db
from app.core.config import settings
from app.core.database import Base
from app.main import app
from app.models.agent import Agent, AgentStatusCurr
from app.models.server import Server, ServerStatusCurr
from app.models.system import SysUser


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SessionFactory = sessionmaker(bind=engine)
Base.metadata.create_all(
    engine,
    tables=[
        SysUser.__table__,
        Server.__table__,
        ServerStatusCurr.__table__,
        Agent.__table__,
        AgentStatusCurr.__table__,
    ],
)


def override_get_db():
    db = SessionFactory()
    try:
        yield db
    finally:
        db.close()


def reset_data():
    with Session(engine) as session:
        for table in reversed([Agent.__table__, Server.__table__, SysUser.__table__]):
            session.execute(table.delete())
        session.add(SysUser(
            user_id=1,
            login_id="viewer",
            user_name="Viewer",
            password_hash="unused",
            status_code="ACTIVE",
            use_yn="Y",
        ))
        session.add(Server(
            server_id=1,
            server_uid="server-1",
            server_name="server-1",
            host_name="host-1",
            mgmt_ip="10.0.0.1",
            os_type_code="LINUX",
            use_yn="Y",
        ))
        session.add(Agent(
            agent_id=1,
            agent_uid="agent-1",
            server_id=1,
            status_code="APPROVED",
            agent_version="1.0.0",
        ))
        session.commit()


def test_list_endpoints_preserve_auth_and_response_contracts():
    app.dependency_overrides[get_db] = override_get_db
    reset_data()
    client = TestClient(app)
    token = jwt.encode({"sub": "viewer"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    headers = {"Authorization": f"Bearer {token}"}
    try:
        assert client.get("/api/v1/servers").status_code == 401
        assert client.get("/api/v1/agents").status_code == 401

        servers = client.get("/api/v1/servers", headers=headers)
        assert servers.status_code == 200
        server = servers.json()["data"][0]
        assert servers.json()["success"] is True
        assert server["server_id"] == 1
        assert server["composite_status"] == "UNKNOWN"

        agents = client.get("/api/v1/agents", headers=headers)
        assert agents.status_code == 200
        agent = agents.json()["data"][0]
        assert agents.json()["success"] is True
        assert agent["agent_id"] == 1
        assert agent["agent_status"] == "UNKNOWN"
        assert agent["host_name"] == "host-1"
    finally:
        app.dependency_overrides.clear()
