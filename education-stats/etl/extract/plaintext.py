"""1370-1375 (and part of 1379) yearbooks: Word-exported HTML whose tables are *plain
text* (ASCII-art, the letter "ا" used as the column rule) inside a single cell.

Not parsed yet -- see docs/inventory.md "Gaps". The national figures for these years are
still recovered from the historic rows of later yearbooks (1380, 1381, ...), which the
grid parsers read. Returning no tables keeps the unit visible in the run log.
"""

from __future__ import annotations

from etl.discover import Unit
from etl.tables import RawTable


def rawtables(u: Unit) -> list[RawTable]:
    return []
