"""Apply reviewed, idempotent Oracle 11g additive schema changes.

This tool never runs schema changes implicitly.  `--apply` is required. Oracle
DDL auto-commits, so every alteration is prechecked and rechecked on an Oracle
concurrent-DDL error before it can be reported as a failure.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


@dataclass(frozen=True)
class AdditiveColumn:
    table_name: str
    column_name: str
    ddl_type: str


REQUIRED_COLUMNS = (
    AdditiveColumn("MON_SERVER", "SERVER_GROUP", "VARCHAR2(100)"),
    AdditiveColumn("MON_SERVER", "TAGS", "VARCHAR2(500)"),
)


def missing_columns(connection, schema: str) -> list[AdditiveColumn]:
    missing: list[AdditiveColumn] = []
    for column in REQUIRED_COLUMNS:
        exists = connection.execute(
            text(
                "SELECT COUNT(*) FROM all_tab_columns "
                "WHERE owner = :owner AND table_name = :table_name "
                "AND column_name = :column_name"
            ),
            {
                "owner": schema.upper(),
                "table_name": column.table_name,
                "column_name": column.column_name,
            },
        ).scalar_one()
        if exists == 0:
            missing.append(column)
    return missing


def apply_missing_columns(connection, schema: str) -> list[AdditiveColumn]:
    applied: list[AdditiveColumn] = []
    for column in missing_columns(connection, schema):
        try:
            # Names and DDL types are module constants, never command-line input.
            connection.execute(
                text(
                    f"ALTER TABLE {schema}.{column.table_name} "
                    f"ADD ({column.column_name} {column.ddl_type})"
                )
            )
            applied.append(column)
        except DBAPIError:
            # Another serialized deploy may have just created the same column.
            # Re-read the data dictionary: accept only that exact completed state.
            still_missing = {
                item.column_name for item in missing_columns(connection, schema)
            }
            if column.column_name in still_missing:
                raise
    return applied


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check or apply the reviewed Oracle additive schema change."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply missing reviewed columns. Omit for a read-only check.",
    )
    args = parser.parse_args()

    from app.core.config import configure_runtime_settings, get_database_url

    settings = configure_runtime_settings()
    from app.core.database import create_database_engine

    engine = create_database_engine(get_database_url(settings), db_schema=settings.DB_SCHEMA)
    with engine.connect() as connection:
        missing = missing_columns(connection, settings.DB_SCHEMA)
        if not missing:
            print("Oracle additive schema is already current.")
            return 0
        if not args.apply:
            print("Missing reviewed columns: " + ", ".join(
                f"{column.table_name}.{column.column_name}" for column in missing
            ))
            print("Re-run with --apply to make this explicit Oracle DDL change.")
            return 2
        applied = apply_missing_columns(connection, settings.DB_SCHEMA)

    if applied:
        print("Applied reviewed additive columns: " + ", ".join(
            f"{column.table_name}.{column.column_name}" for column in applied
        ))
    else:
        print("Oracle additive schema was updated concurrently and is current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
