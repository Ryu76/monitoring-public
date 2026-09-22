import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

TEST_SETTINGS = {
    "DB_USER": "test",
    "DB_PASSWORD": "test",
    "DB_HOST": "localhost",
    "DB_PORT": "1521",
    "DB_SERVICE_NAME": "TEST",
    "DB_SCHEMA": "example_db_user",
    "SECRET_KEY": "test",
}
os.environ.update(TEST_SETTINGS)

from app.api.dependencies import get_db
from app.core.database import Base
from app.main import app


@pytest.fixture
def sqlite_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def db_session(sqlite_engine):
    session = sessionmaker(autocommit=False, autoflush=False, bind=sqlite_engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def api_client(sqlite_engine):
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=sqlite_engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides = {}


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides = {}
