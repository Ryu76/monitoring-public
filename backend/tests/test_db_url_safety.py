from sqlalchemy.engine.url import make_url


def test_db_url_safety(monkeypatch):
    """Structured URL construction preserves reserved credential characters."""
    import app.core.config as config

    class MockSettings:
        DB_USER = "user@name"
        DB_PASSWORD = "pass/word:123%"
        DB_HOST = "localhost"
        DB_PORT = 1521
        DB_SERVICE_NAME = "TEST"

    monkeypatch.setattr(config, "settings", MockSettings)
    parsed_url = make_url(config.get_database_url())

    assert parsed_url.username == "user@name"
    assert parsed_url.password == "pass/word:123%"
    assert parsed_url.host == "localhost"
    assert parsed_url.port == 1521
    assert parsed_url.query["service_name"] == "TEST"
