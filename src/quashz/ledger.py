"""The rejection ledger: every refused row, with the reason, in three columns.

THREE COLUMNS AND THEY ARE CAPPED THERE. `decision_date`, `reason`, `detail`. No severity, no
owner, no ticket, no routing key. A severity column is a request to ignore the rows below a
threshold, and within a month somebody has decided that a leak is a warning. Typed
classification of failures is a different repository's subject and it is not smuggled in here as
a fourth column.

WHY DuckDB RATHER THAN A LIST. The predicate that decides admission is written as SQL, once,
against the same table a reviewer can query. A refusal reason a reviewer cannot reproduce with
one SELECT is a refusal reason nobody will argue with, and the whole value of a ledger is that a
vendor's engineer can argue with it.
"""

from __future__ import annotations

import datetime
import pathlib
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from .frame import Refusal

COLUMNS = ("decision_date", "reason", "detail")

#: The admission predicate, as one statement. A row is admitted when it is on both sides of it.
ADMISSION_SQL = """
select
    decision_date,
    level,
    slope,
    fx,
    gdp,
    gdp_age_days,
    outcome
from candidate
where outcome is not null
  and latest_yield_date < decision_date
  and outcome_date > latest_yield_date
  and gdp_age_days >= 90
"""


def connect(path: pathlib.Path | None = None) -> Any:
    """A DuckDB connection, in memory unless a caller wants the file to look at afterwards."""
    import duckdb

    return duckdb.connect(str(path) if path else ":memory:")


def write(connection: Any, refusals: Iterable[Refusal]) -> int:
    """Create the ledger and fill it. Returns how many rows it holds."""
    connection.execute(
        """
        create or replace table rejection_ledger (
            decision_date date not null,
            reason text not null,
            detail text not null
        )
        """
    )
    rows = [(refusal.decision_date, refusal.reason, refusal.detail) for refusal in refusals]
    if rows:
        connection.executemany("insert into rejection_ledger values (?, ?, ?)", rows)
    counted: int = connection.execute("select count(*) from rejection_ledger").fetchone()[0]
    return counted


def rate(connection: Any, admitted: int) -> float:
    """The rejection rate, which is the verdict's second number.

    Expressed against everything that was CONSIDERED rather than against everything admitted,
    because a rate whose denominator excludes the rejections is not a rate.
    """
    refused: int = connection.execute("select count(*) from rejection_ledger").fetchone()[0]
    considered = admitted + refused
    return refused / considered if considered else 0.0


def by_reason(connection: Any) -> list[tuple[str, int]]:
    """Every reason with its count, ordered so the output is the same on any two runs."""
    found: Sequence[tuple[str, int]] = connection.execute(
        "select reason, count(*) as n from rejection_ledger group by reason order by reason"
    ).fetchall()
    return [(str(reason), int(count)) for reason, count in found]


Admitted = tuple[datetime.date, float, float, float, float, int, int]


def admit(connection: Any, rows: Iterable[Any]) -> list[Admitted]:
    """Load the candidate rows and apply the admission predicate as SQL.

    The predicate is the artefact, not this function. It is one statement, it is printed by the
    verdict, and a reviewer can paste it into their own DuckDB against the same table.

    The `gdp_age_days >= 90` clause is the one worth arguing with, and it is deliberately in the
    SQL rather than in Python. A quarterly figure is never served in under 115 days in this
    archive, so a row claiming a fresher one is not a fresh row: it is a row built from a
    publication date that was assumed rather than recovered, and the predicate refuses it
    instead of trusting the pipeline that produced it.
    """
    connection.execute(
        """
        create or replace table candidate (
            decision_date date not null,
            latest_yield_date date not null,
            level double not null,
            slope double not null,
            fx double not null,
            gdp double not null,
            gdp_age_days integer not null,
            outcome_date date,
            outcome integer
        )
        """
    )
    payload = [
        (
            row.decision_date,
            row.latest_yield_date,
            row.level,
            row.slope,
            row.fx,
            row.gdp,
            row.gdp_age_days,
            row.outcome_date,
            row.outcome,
        )
        for row in rows
    ]
    if payload:
        connection.executemany("insert into candidate values (?, ?, ?, ?, ?, ?, ?, ?, ?)", payload)
    return [
        (date, float(level), float(slope), float(fx), float(gdp), int(age), int(outcome))
        for date, level, slope, fx, gdp, age, outcome in connection.execute(
            ADMISSION_SQL
        ).fetchall()
    ]
