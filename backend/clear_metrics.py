"""Explicitly clear metric history/current rows through schema-aware ORM deletes."""
import argparse

from sqlalchemy import delete

from app.core.database import SessionLocal
from app.models.resource import MetricCurrent, MetricHistory


def clear_metrics(session) -> tuple[int, int]:
    """Delete history before current state inside the caller's transaction."""
    history_count = session.execute(delete(MetricHistory)).rowcount or 0
    current_count = session.execute(delete(MetricCurrent)).rowcount or 0
    return history_count, current_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Clear monitoring metric data.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform the destructive delete. Omit for a safe refusal.",
    )
    args = parser.parse_args()
    if not args.apply:
        print("Refusing to delete metric data without --apply.")
        return 2

    session = SessionLocal()
    try:
        history_count, current_count = clear_metrics(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print(f"Cleared metric rows: history={history_count}, current={current_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
