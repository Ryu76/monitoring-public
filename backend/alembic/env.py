import os
import sys
from logging.config import fileConfig

import oracledb
from alembic import context
from sqlalchemy import engine_from_config, pool, text

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.core.config import configure_runtime_settings, get_database_url
from app.models import Base

# Direct Alembic, worker, and API invocations must resolve one validated
# encrypted configuration before any database engine is constructed.
settings = configure_runtime_settings()

try:
    oracledb.init_oracle_client()
except Exception:
    pass

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):
    """Keep deployed Oracle indexes/FKs outside autogeneration diffs."""
    return type_ != "index"


def run_migrations_offline() -> None:
    """Generate SQL with the configured schema recorded for Alembic state."""
    context.configure(
        url=get_database_url(settings),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=False,
        include_object=include_object,
        version_table_schema=settings.DB_SCHEMA,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run DDL in the explicit configured Oracle schema, never a login default."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url(settings)
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # DB_SCHEMA is a strict Settings regex, never raw command input.
        connection.execute(text(f"ALTER SESSION SET CURRENT_SCHEMA = {settings.DB_SCHEMA}"))
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=False,
            include_object=include_object,
            version_table_schema=settings.DB_SCHEMA,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
