from __future__ import annotations

from apply_oracle_additive_schema import REQUIRED_COLUMNS, apply_missing_columns, missing_columns


class _ScalarResult:
    def __init__(self, value: int):
        self.value = value

    def scalar_one(self) -> int:
        return self.value


class _Connection:
    def __init__(self, exists: int = 0):
        self.exists = exists
        self.calls: list[tuple[str, dict | None]] = []

    def execute(self, statement, parameters=None):
        self.calls.append((str(statement), parameters))
        if str(statement).lstrip().upper().startswith("SELECT"):
            return _ScalarResult(self.exists)
        return _ScalarResult(0)


def test_missing_columns_uses_bound_dictionary_parameters():
    connection = _Connection(exists=0)

    missing = missing_columns(connection, "example_db_user")

    assert missing == list(REQUIRED_COLUMNS)
    assert len(connection.calls) == len(REQUIRED_COLUMNS)
    for statement, parameters in connection.calls:
        assert "all_tab_columns" in statement
        assert parameters["owner"] == "example_db_user"
        assert parameters["table_name"] == "MON_SERVER"


def test_apply_missing_columns_runs_only_reviewed_constant_ddl():
    connection = _Connection(exists=0)

    applied = apply_missing_columns(connection, "example_db_user")

    assert applied == list(REQUIRED_COLUMNS)
    statements = [statement for statement, _ in connection.calls]
    ddl_statements = [statement for statement in statements if statement.lstrip().upper().startswith("ALTER TABLE")]
    assert ddl_statements == [
        "ALTER TABLE example_db_user.MON_SERVER ADD (SERVER_GROUP VARCHAR2(100))",
        "ALTER TABLE example_db_user.MON_SERVER ADD (TAGS VARCHAR2(500))",
    ]


def test_apply_skips_ddl_when_columns_already_exist():
    connection = _Connection(exists=1)

    assert apply_missing_columns(connection, "example_db_user") == []
    assert all(not statement.lstrip().upper().startswith("ALTER TABLE") for statement, _ in connection.calls)
