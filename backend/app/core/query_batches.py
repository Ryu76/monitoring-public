"""Small Oracle-compatible query helpers shared by ORM request paths."""
from collections.abc import Collection, Iterator
from typing import TypeVar


T = TypeVar("T")
ORACLE_IN_LIST_CHUNK_SIZE = 999


def oracle_in_chunks(values: Collection[T]) -> Iterator[tuple[T, ...]]:
    """Split IN-list values below Oracle's 1,000-expression limit."""
    items = tuple(values)
    for offset in range(0, len(items), ORACLE_IN_LIST_CHUNK_SIZE):
        yield items[offset : offset + ORACLE_IN_LIST_CHUNK_SIZE]
