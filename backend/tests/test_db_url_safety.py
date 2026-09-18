import pytest
from app.core.config import get_database_url
from sqlalchemy.engine import URL

def test_db_url_safety(monkeypatch):
    """Ensure database URL is constructed using URL.create, handling special chars safely."""
    monkeypatch.setenv("DB_USER", "user@name")
    monkeypatch.setenv("DB_PASSWORD", "pass/word:123%")
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "1521")
    class MockSettings:
        DB_USER = "user@name"
        DB_PASSWORD = "pass/word:123%"
        DB_HOST = "localhost"
        DB_PORT = 1521
        DB_SERVICE_NAME = "TEST"

    monkeypatch.setattr("app.core.config.settings", MockSettings)

    url_str = get_database_url()

    # URL string should be properly encoded or constructed via SQLAlchemy
    # Let's parse it back using SQLAlchemy URL and check properties
    from sqlalchemy.engine.url import make_url
    parsed_url = make_url(url_str)

    assert parsed_url.username == "user@name"
    assert parsed_url.password == "pass/word:123%"
    assert parsed_url.host == "localhost"
    assert parsed_url.port == 1521
    assert parsed_url.query["service_name"] == "TEST"
