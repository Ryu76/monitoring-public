"""Add missing Oracle tables and sequences
Revision ID: c2a445586611
Revises: 84712a097b58
Create Date: 2026-09-18 10:28:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'c2a445586611'
down_revision: Union[str, None] = '84712a097b58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# tables that need sequence/trigger for PK
TABLES_WITH_SEQ = {
    'mon_check_target': 'check_target_id',
    'mon_check_result_hist': 'check_result_id',
    'mon_metric_hist': 'metric_hist_id',
    'mon_alert_outbox': 'outbox_id',
    'mon_alert_hist': 'history_id',
    'mon_incident': 'incident_id',
    'mon_incident_action': 'action_id',
    'ext_health_check': 'id',
    'ext_remote_cmd_approval': 'id',
    'ext_config_version': 'id',
    'ext_ha_cluster_state': 'id',
}

def upgrade() -> None:
    conn = op.get_bind()
    dialect_name = conn.dialect.name

    if dialect_name == 'oracle':
        for table_name, pk_col in TABLES_WITH_SEQ.items():
            seq_name = f"seq_{table_name}"
            trg_name = f"trg_{table_name}"

            # Idempotent sequence creation
            op.execute(sa.text(f"""
                DECLARE
                    cnt NUMBER;
                BEGIN
                    SELECT count(*) INTO cnt FROM user_sequences WHERE sequence_name = UPPER('{seq_name}');
                    IF cnt = 0 THEN
                        EXECUTE IMMEDIATE 'CREATE SEQUENCE {seq_name} START WITH 1 INCREMENT BY 1';
                    END IF;
                END;
            """))

            # Idempotent trigger creation
            op.execute(sa.text(f"""
                CREATE OR REPLACE TRIGGER {trg_name}
                BEFORE INSERT ON {table_name}
                FOR EACH ROW
                BEGIN
                    IF :NEW.{pk_col} IS NULL THEN
                        SELECT {seq_name}.NEXTVAL INTO :NEW.{pk_col} FROM DUAL;
                    END IF;
                END;
            """))

    op.create_table(
        'mon_metric_receipt_ledger',
        sa.Column('batch_uid', sa.String(40), nullable=False, primary_key=True),
        sa.Column('agent_id', sa.Integer(), nullable=False),
        sa.Column('received_at', sa.TIMESTAMP(), nullable=False),
        sa.Column('item_count', sa.Integer(), nullable=False)
    )

def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == 'oracle':
        for table_name, _ in TABLES_WITH_SEQ.items():
            seq_name = f"seq_{table_name}"
            trg_name = f"trg_{table_name}"
            # Oracle 11g lacks DROP TRIGGER IF EXISTS, so we catch it
            op.execute(sa.text(f"""
                BEGIN
                   EXECUTE IMMEDIATE 'DROP TRIGGER {trg_name}';
                EXCEPTION
                   WHEN OTHERS THEN
                      IF SQLCODE != -4080 THEN RAISE; END IF;
                END;
            """))
            op.execute(sa.text(f"""
                DECLARE
                    cnt NUMBER;
                BEGIN
                    SELECT count(*) INTO cnt FROM user_sequences WHERE sequence_name = UPPER('{seq_name}');
                    IF cnt > 0 THEN
                        EXECUTE IMMEDIATE 'DROP SEQUENCE {seq_name}';
                    END IF;
                END;
            """))
    op.drop_table('mon_metric_receipt_ledger')
