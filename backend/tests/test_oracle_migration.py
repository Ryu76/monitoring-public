from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260918_1028_c2a445586611_add_missing_oracle_tables.py"
)


def test_oracle_operational_migration_covers_all_required_objects_in_order():
    """Keep Oracle 11g operational DDL complete and non-destructive by contract."""
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    required_tables = {
        "mon_metric_receipt_ledger",
        "mon_check_snapshot_watermark",
        "mon_alert_outbox",
        "mon_alert_hist",
        "ext_health_check",
        "ext_remote_cmd_approval",
        "ext_config_version",
        "ext_ha_cluster_state",
    }
    for table_name in required_tables:
        assert f'"{table_name}":' in source

    # Legacy metric/check tables must only gain safe generators, not be dropped.
    for table_name, column_name in {
        "mon_metric_hist": "metric_hist_id",
        "mon_check_target": "check_target_id",
        "mon_check_result_hist": "check_result_id",
    }.items():
        assert f'"{table_name}": "{column_name}"' in source
    assert "SELECT NVL(MAX({pk_column}), 0) + 1" in source

    # New tables precede indexes and generators; Oracle 11g generators cannot
    # use identity/autoincrement and must be guarded by data-dictionary checks.
    assert source.index("for table_name, ddl in ORACLE_TABLE_DDL.items()") < source.index(
        "for index_name, ddl in ORACLE_INDEXES.items()"
    ) < source.index("for table_name, pk_column in SEQUENCE_TRIGGER_TABLES.items()")
    assert "user_sequences" in source
    assert "user_triggers" in source
    assert "CREATE TRIGGER" in source
    # SQLAlchemy treats :NEW as a bind parameter unless the Oracle trigger
    # pseudorecord colon is escaped in the SQL text source.
    assert "\\\\:NEW.{pk_column}" in source
    assert "AUTOINCREMENT" not in source.upper()
    assert "def downgrade()" in source and "pass" in source
