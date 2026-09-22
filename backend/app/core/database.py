import oracledb
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import get_database_url, settings

# Oracle 11g compatibility may use Thick mode when an Instant Client exists.
try:
    oracledb.init_oracle_client()
except Exception:
    # Thin mode remains supported. Avoid printing machine-specific client paths.
    pass


def create_database_engine(
    database_url: URL | str | None = None,
    db_schema: str | None = None,
) -> Engine:
    """Create an engine with Oracle-only schema translation for schema-less models."""
    engine = create_engine(database_url or get_database_url(), echo=False)
    if engine.dialect.name == "oracle":
        return engine.execution_options(
            schema_translate_map={None: db_schema or settings.DB_SCHEMA}
        )
    return engine


engine = create_database_engine()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()
