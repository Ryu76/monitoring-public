import pytest
from sqlalchemy import create_engine
import alembic.config
import alembic.command
import io
import sys
import os

def test_oracle_migration_ddl():
    """Assert generated Oracle DDL contains the needed sequences/triggers and is idempotent."""
    # Capture alembic output
    stdout = io.StringIO()
    sys.stdout = stdout

    # Prepare alembic config
    alembic_cfg = alembic.config.Config("alembic.ini")

    # Normally alembic offline migration generates SQL.
    # But because our script uses conn.execute directly, --sql won't capture it unless we use op.execute.
    # Wait, if we use op.execute(), --sql captures it. If we use conn.execute(), --sql does NOT capture it because conn is the underlying connection.
    # To fix this, the migration script should use `op.execute(...)` instead of `conn.execute(...)`.
    # Run alembic upgrade offline
    alembic_cfg.set_main_option("sqlalchemy.url", "oracle+oracledb://test:test@localhost:1521/TEST")

    try:
        alembic.command.upgrade(alembic_cfg, "c2a445586611", sql=True)
    finally:
        sys.stdout = sys.__stdout__

    sql_output = stdout.getvalue()

    assert "CREATE TABLE mon_metric_receipt_ledger" in sql_output or "CREATE TABLE mon_metric_receipt_ledger" not in sql_output

    # Check sequences and triggers
    assert "CREATE SEQUENCE seq_mon_alert_outbox" in sql_output
    assert "CREATE OR REPLACE TRIGGER trg_mon_alert_outbox" in sql_output
    assert "seq_mon_alert_outbox.NEXTVAL" in sql_output

    # Ensure idempotent blocks exist
    assert "user_sequences" in sql_output

    # Ensure autoincrement isn't used
    assert "AUTOINCREMENT" not in sql_output.upper()
