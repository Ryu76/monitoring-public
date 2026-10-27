"""Idempotently seed the standard metric definitions through the ORM."""
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.resource import MetricDef

METRICS = [
    ("CPU_USAGE_PCT", "CPU 사용률 (%)", "CPU", "FLOAT", "PERCENT", "AVG"),
    ("MEM_USAGE_PCT", "메모리 사용률 (%)", "MEMORY", "FLOAT", "PERCENT", "AVG"),
    ("MEM_AVAILABLE_BYTES", "사용 가능 메모리 (Bytes)", "MEMORY", "BIGINT", "BYTES", "AVG"),
    ("DISK_USAGE_PCT", "디스크 사용률 (%)", "DISK", "FLOAT", "PERCENT", "AVG"),
    ("DISK_AVAILABLE_BYTES", "사용 가능 디스크 (Bytes)", "DISK", "BIGINT", "BYTES", "AVG"),
    ("NET_BYTES_SENT", "네트워크 송신 (Bytes)", "NETWORK", "BIGINT", "BYTES", "SUM"),
    ("NET_BYTES_RECV", "네트워크 수신 (Bytes)", "NETWORK", "BIGINT", "BYTES", "SUM"),
    ("PROCESS_CPU_PCT", "Top Process CPU Usage (%)", "PROCESS", "FLOAT", "PERCENT", "AVG"),
    ("PROCESS_MEM_PCT", "Top Process Memory Usage (%)", "PROCESS", "FLOAT", "PERCENT", "AVG"),
    ("PORT_LISTEN", "TCP Port Listening Status", "PORT", "FLOAT", "BOOLEAN", "LAST"),
    ("SERVICE_STATUS", "Service Running Status", "SERVICE", "FLOAT", "BOOLEAN", "LAST"),
]


def seed_metric_definitions(session) -> list[str]:
    """Add only missing definitions using one schema-aware ORM preload query."""
    codes = {metric[0] for metric in METRICS}
    existing_codes = set(
        session.execute(
            select(MetricDef.metric_code).where(MetricDef.metric_code.in_(codes))
        ).scalars()
    )
    inserted = []
    created_at = datetime.now(timezone.utc)
    for code, name, category, value_type, unit, agg_type in METRICS:
        if code in existing_codes:
            continue
        session.add(MetricDef(
            metric_code=code,
            metric_name=name,
            category_code=category,
            value_type_code=value_type,
            unit_code=unit,
            agg_type_code=agg_type,
            windows_support_yn="Y",
            linux_support_yn="Y",
            use_yn="Y",
            created_at=created_at,
        ))
        inserted.append(code)
    return inserted


def main() -> int:
    session = SessionLocal()
    try:
        inserted = seed_metric_definitions(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    for code in inserted:
        print(f"Inserted: {code}")
    print(f"Done. inserted={len(inserted)} existing={len(METRICS) - len(inserted)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
