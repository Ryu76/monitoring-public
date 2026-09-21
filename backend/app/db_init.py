"""Deprecated runtime schema helper.

Operational schema is created exclusively by Alembic revision c2a445586611.
This module intentionally contains no DDL and must not be called from API or
worker startup paths.
"""


def ensure_operational_tables(*_args, **_kwargs) -> None:
    """Retained only for import compatibility; schema deployment uses Alembic."""
    raise RuntimeError(
        "Runtime schema creation is disabled; run Alembic migrations before starting services."
    )
