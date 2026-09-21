"""Create Phase 09/10 operational tables for Oracle 11g.

Revision ID: c2a445586611
Revises: 84712a097b58
Create Date: 2026-09-18 10:28:00.000000

The pre-existing monitoring schema is not owned by Alembic.  This revision is
therefore deliberately additive: it creates only Phase 09/10 objects and its
downgrade is non-destructive.  Oracle 11g has no ``CREATE ... IF NOT EXISTS``;
the Oracle blocks below check the data dictionary before issuing DDL.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2a445586611"
down_revision: Union[str, None] = "84712a097b58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Every table in this revision is new operational state.  Do not put existing
# mon_* or sys_* tables here: this migration must not redefine production data.
ORACLE_TABLE_DDL = {
    "mon_metric_receipt_ledger": """
        CREATE TABLE mon_metric_receipt_ledger (
            batch_uid VARCHAR2(40) NOT NULL,
            agent_id NUMBER(10) NOT NULL,
            received_at TIMESTAMP NOT NULL,
            item_count NUMBER(10) NOT NULL,
            CONSTRAINT pk_metric_receipt_ledger PRIMARY KEY (batch_uid),
            CONSTRAINT fk_metric_receipt_agent FOREIGN KEY (agent_id)
                REFERENCES mon_agent (agent_id)
        )
    """,
    "mon_check_target": """
        CREATE TABLE mon_check_target (
            check_target_id NUMBER(10) NOT NULL,
            server_id NUMBER(10) NOT NULL,
            target_type_code VARCHAR2(30) NOT NULL,
            target_name VARCHAR2(200) NOT NULL,
            use_yn CHAR(1) DEFAULT 'Y' NOT NULL,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            CONSTRAINT pk_check_target PRIMARY KEY (check_target_id),
            CONSTRAINT fk_check_target_server FOREIGN KEY (server_id)
                REFERENCES mon_server (server_id)
        )
    """,
    "mon_check_result_hist": """
        CREATE TABLE mon_check_result_hist (
            check_result_id NUMBER(10) NOT NULL,
            server_id NUMBER(10) NOT NULL,
            agent_id NUMBER(10),
            target_type_code VARCHAR2(30) NOT NULL,
            target_name VARCHAR2(200) NOT NULL,
            metric_code VARCHAR2(60) NOT NULL,
            metric_value NUMBER,
            string_value VARCHAR2(1000),
            status_code VARCHAR2(30),
            collected_at TIMESTAMP NOT NULL,
            received_at TIMESTAMP NOT NULL,
            CONSTRAINT pk_check_result_hist PRIMARY KEY (check_result_id),
            CONSTRAINT fk_check_result_server FOREIGN KEY (server_id)
                REFERENCES mon_server (server_id),
            CONSTRAINT fk_check_result_agent FOREIGN KEY (agent_id)
                REFERENCES mon_agent (agent_id),
            CONSTRAINT fk_check_result_metric FOREIGN KEY (metric_code)
                REFERENCES mon_metric_def (metric_code)
        )
    """,
    "mon_check_snapshot_watermark": """
        CREATE TABLE mon_check_snapshot_watermark (
            server_id NUMBER(10) NOT NULL,
            metric_code VARCHAR2(60) NOT NULL,
            collected_at TIMESTAMP NOT NULL,
            received_at TIMESTAMP NOT NULL,
            CONSTRAINT pk_check_snapshot_watermark PRIMARY KEY (server_id, metric_code),
            CONSTRAINT fk_snapshot_server FOREIGN KEY (server_id)
                REFERENCES mon_server (server_id),
            CONSTRAINT fk_snapshot_metric FOREIGN KEY (metric_code)
                REFERENCES mon_metric_def (metric_code)
        )
    """,
    "mon_alert_outbox": """
        CREATE TABLE mon_alert_outbox (
            outbox_id NUMBER(10) NOT NULL,
            event_uid VARCHAR2(40) NOT NULL,
            policy_id VARCHAR2(50) NOT NULL,
            target VARCHAR2(200) NOT NULL,
            title VARCHAR2(500) NOT NULL,
            message CLOB NOT NULL,
            status VARCHAR2(30) DEFAULT 'PENDING' NOT NULL,
            retry_count NUMBER(10) DEFAULT 0 NOT NULL,
            created_at TIMESTAMP NOT NULL,
            CONSTRAINT pk_alert_outbox PRIMARY KEY (outbox_id),
            CONSTRAINT fk_alert_outbox_event FOREIGN KEY (event_uid)
                REFERENCES mon_event (event_uid),
            CONSTRAINT fk_alert_outbox_policy FOREIGN KEY (policy_id)
                REFERENCES mon_alert_policy (policy_id)
        )
    """,
    "mon_alert_hist": """
        CREATE TABLE mon_alert_hist (
            history_id NUMBER(10) NOT NULL,
            event_uid VARCHAR2(40),
            policy_id VARCHAR2(50),
            target VARCHAR2(200),
            title VARCHAR2(500),
            message CLOB,
            status VARCHAR2(30),
            error_msg CLOB,
            sent_at TIMESTAMP NOT NULL,
            CONSTRAINT pk_alert_hist PRIMARY KEY (history_id),
            CONSTRAINT fk_alert_hist_event FOREIGN KEY (event_uid)
                REFERENCES mon_event (event_uid),
            CONSTRAINT fk_alert_hist_policy FOREIGN KEY (policy_id)
                REFERENCES mon_alert_policy (policy_id)
        )
    """,
    "ext_health_check": """
        CREATE TABLE ext_health_check (
            id NUMBER(10) NOT NULL,
            target_type VARCHAR2(30) NOT NULL,
            target_url_or_path VARCHAR2(500) NOT NULL,
            status VARCHAR2(30) NOT NULL,
            mock_response CLOB,
            checked_at TIMESTAMP,
            CONSTRAINT pk_ext_health_check PRIMARY KEY (id)
        )
    """,
    "ext_remote_cmd_approval": """
        CREATE TABLE ext_remote_cmd_approval (
            id NUMBER(10) NOT NULL,
            command_type VARCHAR2(100) NOT NULL,
            target_server VARCHAR2(100) NOT NULL,
            approval_state VARCHAR2(30) NOT NULL,
            dry_run_result CLOB,
            audit_event CLOB,
            requested_by VARCHAR2(100),
            requested_at TIMESTAMP,
            CONSTRAINT pk_ext_remote_cmd_approval PRIMARY KEY (id)
        )
    """,
    "ext_config_version": """
        CREATE TABLE ext_config_version (
            id NUMBER(10) NOT NULL,
            component_name VARCHAR2(100) NOT NULL,
            version_tag VARCHAR2(50) NOT NULL,
            config_payload CLOB,
            rollback_metadata CLOB,
            created_at TIMESTAMP,
            CONSTRAINT pk_ext_config_version PRIMARY KEY (id),
            CONSTRAINT uq_ext_config_version UNIQUE (component_name, version_tag)
        )
    """,
    "ext_ha_cluster_state": """
        CREATE TABLE ext_ha_cluster_state (
            id NUMBER(10) NOT NULL,
            node_name VARCHAR2(100) NOT NULL,
            role VARCHAR2(30) NOT NULL,
            health_state VARCHAR2(30) NOT NULL,
            last_heartbeat TIMESTAMP,
            CONSTRAINT pk_ext_ha_cluster_state PRIMARY KEY (id),
            CONSTRAINT uq_ext_ha_node_name UNIQUE (node_name)
        )
    """,
}

ORACLE_INDEXES = {
    "ix_metric_receipt_agent_time": "CREATE INDEX ix_metric_receipt_agent_time ON mon_metric_receipt_ledger (agent_id, received_at)",
    "ix_check_target_server_type": "CREATE INDEX ix_check_target_server_type ON mon_check_target (server_id, target_type_code, use_yn)",
    "ix_check_result_server_time": "CREATE INDEX ix_check_result_server_time ON mon_check_result_hist (server_id, metric_code, collected_at)",
    "ix_check_result_agent_time": "CREATE INDEX ix_check_result_agent_time ON mon_check_result_hist (agent_id, collected_at)",
    "ix_alert_outbox_status_time": "CREATE INDEX ix_alert_outbox_status_time ON mon_alert_outbox (status, created_at)",
    "ix_alert_outbox_event": "CREATE INDEX ix_alert_outbox_event ON mon_alert_outbox (event_uid)",
    "ix_alert_hist_event_time": "CREATE INDEX ix_alert_hist_event_time ON mon_alert_hist (event_uid, sent_at)",
    "ix_ext_health_status_time": "CREATE INDEX ix_ext_health_status_time ON ext_health_check (status, checked_at)",
    "ix_ext_cmd_state_time": "CREATE INDEX ix_ext_cmd_state_time ON ext_remote_cmd_approval (approval_state, requested_at)",
}

# Numeric identifiers require explicit Oracle 11g generators. Newly created
# tables start empty; baseline metric/check tables are never re-created but get
# a non-destructive generator backfill from MAX(pk)+1 when one is absent.
SEQUENCE_TRIGGER_TABLES = {
    "mon_metric_hist": "metric_hist_id",
    "mon_check_target": "check_target_id",
    "mon_check_result_hist": "check_result_id",
    "mon_alert_outbox": "outbox_id",
    "mon_alert_hist": "history_id",
    "ext_health_check": "id",
    "ext_remote_cmd_approval": "id",
    "ext_config_version": "id",
    "ext_ha_cluster_state": "id",
}


def _oracle_create_if_missing(kind: str, name: str, ddl: str) -> None:
    """Emit Oracle 11g-compatible idempotent DDL without replacing old objects."""
    dictionary = {
        "TABLE": "user_tables",
        "INDEX": "user_indexes",
        "SEQUENCE": "user_sequences",
        "TRIGGER": "user_triggers",
    }[kind]
    # q'~...~' prevents values such as DEFAULT 'Y' from breaking the dynamic SQL.
    op.execute(sa.text(f"""
        DECLARE
            object_count NUMBER;
        BEGIN
            SELECT COUNT(*) INTO object_count
              FROM {dictionary}
             WHERE {kind}_name = UPPER('{name}');
            IF object_count = 0 THEN
                EXECUTE IMMEDIATE q'~{ddl.strip()}~';
            END IF;
        END;
    """))


def _oracle_create_sequence_from_max(table_name: str, pk_column: str, sequence_name: str) -> None:
    """Create a missing sequence above existing IDs without changing old rows."""
    op.execute(sa.text(f"""
        DECLARE
            object_count NUMBER;
            next_id NUMBER;
        BEGIN
            SELECT COUNT(*) INTO object_count
              FROM user_sequences WHERE sequence_name = UPPER('{sequence_name}');
            IF object_count = 0 THEN
                SELECT NVL(MAX({pk_column}), 0) + 1 INTO next_id FROM {table_name};
                EXECUTE IMMEDIATE 'CREATE SEQUENCE {sequence_name} START WITH ' ||
                    TO_CHAR(next_id) || ' INCREMENT BY 1 NOCACHE';
            END IF;
        END;
    """))


def _upgrade_oracle() -> None:
    # Tables must exist before dependent indexes, sequences, or triggers.
    for table_name, ddl in ORACLE_TABLE_DDL.items():
        _oracle_create_if_missing("TABLE", table_name, ddl)

    for index_name, ddl in ORACLE_INDEXES.items():
        _oracle_create_if_missing("INDEX", index_name, ddl)

    for table_name, pk_column in SEQUENCE_TRIGGER_TABLES.items():
        sequence_name = f"seq_{table_name}"
        trigger_name = f"trg_{table_name}"
        _oracle_create_sequence_from_max(table_name, pk_column, sequence_name)
        _oracle_create_if_missing(
            "TRIGGER", trigger_name,
            f"""CREATE TRIGGER {trigger_name}
                BEFORE INSERT ON {table_name}
                FOR EACH ROW
                WHEN (NEW.{pk_column} IS NULL)
                BEGIN
                    SELECT {sequence_name}.NEXTVAL INTO \\:NEW.{pk_column} FROM DUAL;
                END;""",
        )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "oracle":
        raise RuntimeError("c2a445586611 is an Oracle 11g operational-schema migration")
    _upgrade_oracle()


def downgrade() -> None:
    """Intentionally non-destructive.

    This database was historically managed outside Alembic, so an inferred
    downgrade cannot prove which rows or same-named objects pre-dated this
    revision.  Leaving additive operational objects in place is the safe
    rollback behaviour; application rollback is handled by code deployment.
    """
    pass
