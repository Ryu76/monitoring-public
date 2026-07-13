import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Engine


logger = logging.getLogger(__name__)


def ensure_operational_tables(engine: Engine):
    """Create runtime tables and seed metric definitions required by newer UI features."""
    with engine.begin() as conn:
        _ensure_check_target_table(conn)
        _ensure_check_result_hist_table(conn)
        _ensure_metric_def(
            conn,
            "PROCESS_STATUS",
            "Process Running Status",
            "PROCESS",
            "FLOAT",
            "BOOLEAN",
            "LAST",
        )


def _ensure_check_target_table(conn):
    try:
        conn.execute(text("SELECT 1 FROM mon_check_target WHERE 1 = 0"))
        return
    except Exception:
        logger.info("Creating mon_check_target table.")

    conn.execute(text("""
        CREATE TABLE mon_check_target (
            check_target_id NUMBER NOT NULL PRIMARY KEY,
            server_id NUMBER NOT NULL,
            target_type_code VARCHAR2(30) NOT NULL,
            target_name VARCHAR2(200) NOT NULL,
            use_yn CHAR(1) DEFAULT 'Y' NOT NULL,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """))


def _ensure_check_result_hist_table(conn):
    try:
        conn.execute(text("SELECT 1 FROM mon_check_result_hist WHERE 1 = 0"))
        return
    except Exception:
        logger.info("Creating mon_check_result_hist table.")

    conn.execute(text("""
        CREATE TABLE mon_check_result_hist (
            check_result_id NUMBER NOT NULL PRIMARY KEY,
            server_id NUMBER NOT NULL,
            agent_id NUMBER,
            target_type_code VARCHAR2(30) NOT NULL,
            target_name VARCHAR2(200) NOT NULL,
            metric_code VARCHAR2(60) NOT NULL,
            metric_value NUMBER,
            string_value VARCHAR2(1000),
            status_code VARCHAR2(30),
            collected_at TIMESTAMP NOT NULL,
            received_at TIMESTAMP NOT NULL
        )
    """))


def _ensure_metric_def(conn, metric_code: str, metric_name: str, category: str, value_type: str, unit: str, agg_type: str):
    existing = conn.execute(
        text("SELECT COUNT(1) FROM mon_metric_def WHERE metric_code = :metric_code"),
        {"metric_code": metric_code},
    ).scalar()
    if existing:
        return

    conn.execute(
        text("""
            INSERT INTO mon_metric_def (
                metric_code,
                metric_name,
                category_code,
                value_type_code,
                unit_code,
                agg_type_code,
                windows_support_yn,
                linux_support_yn,
                use_yn,
                created_at
            )
            VALUES (
                :metric_code,
                :metric_name,
                :category_code,
                :value_type_code,
                :unit_code,
                :agg_type_code,
                'Y',
                'Y',
                'Y',
                :created_at
            )
        """),
        {
            "metric_code": metric_code,
            "metric_name": metric_name,
            "category_code": category,
            "value_type_code": value_type,
            "unit_code": unit,
            "agg_type_code": agg_type,
            "created_at": datetime.now(timezone.utc),
        },
    )
