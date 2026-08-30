"""Building the training frame, and refusing the rows that cannot honestly be in it.

THE REFUSAL THIS REPOSITORY IS FOR. A row is refused when its OUTCOME was not yet decidable at
the moment the decision would have been made. That refusal cannot be expressed by a feature
store, an expectation suite or a data contract, because none of them has a label: they can all
tell you a column is null, none of them can tell you that the thing you are trying to learn had
not happened yet.

THREE CLOCKS RUN HERE and confusing any two of them is a leak.

    the observation label   the day the number is ABOUT
    knowable_from          the day the publisher first served that number, recovered from the
                           archive by bisection, never assumed from a lag table
    the decision date      the day a decision would have been made, which is the only clock a
                           model is allowed to look backwards from

MEASURED, NOT ASSUMED. The H.15 yields carry a release lag of one day: DGS10 for 2024-01-02 was
first served on 2024-01-03. Real GDP labelled 2024-01-01 was first served on 2024-04-25, 115
days later. Both come from `knowable_from.csv`, which `scripts/capture_knowable.py` recovered by
bisecting ALFRED vintages, and neither is written down anywhere in the data itself.

ONE OF THE FOUR SERIES HAS NO MEASURED LAG, said here rather than left to be found. DGS10's was
recovered and T10Y2Y borrows it, the two being H.15 dailies out of one release. DEXUSEU was
never bisected at all, so `fx` below is read at the observation labelled the decision date
itself, on a lag nothing here measured. SOURCE.json calls it a noon buying rate, and a noon rate
is not knowable on the morning of the same day. Recovering it and applying it moves every
measured number that reads this frame, so it is an open item held still by a test rather than a
quiet one.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from . import corpus

#: The horizon, in trading days, between the decision and the outcome it is judged on.
HORIZON = 20

#: The release lag for the daily H.15 series, in calendar days, as recovered by the bisection.
#: It is asserted against `knowable_from.csv` in the tests rather than trusted here.
YIELD_RELEASE_LAG_DAYS = 1


@dataclass(frozen=True)
class Row:
    """One decision date, the features knowable by then, and the outcome if it is decidable."""

    decision_date: datetime.date
    latest_yield_date: datetime.date
    level: float
    slope: float
    fx: float
    #: The most recent quarterly figure the publisher had SERVED by this morning, among the
    #: quarters the archive was bisected for, and how old the period it describes already was.
    #: The age is a feature in its own right: a model given a number without being told how
    #: stale it is cannot tell a fresh release from a figure five months old, and on this series
    #: the difference is a quarter of a year. Past the last recovered quarter the same figure is
    #: served to every later decision date and the age climbs, so at the very end of the corpus
    #: it measures the reach of the bisection as well as the publisher's lag.
    gdp: float
    gdp_age_days: int
    outcome_date: datetime.date | None
    outcome: int | None


@dataclass(frozen=True)
class Refusal:
    """Three columns. No severity, no routing, no owner, no ticket.

    A rejection ledger grows a severity column the week after it is built, and a severity column
    is a request to ignore the rows below a threshold. Typed classification of a failure is a
    different repository's subject and it is not smuggled in here as a fourth column.
    """

    decision_date: datetime.date
    reason: str
    detail: str


REASONS = (
    "outcome not decidable at the decision date",
    "no yield published by the decision date",
    "no quarterly figure published by the decision date",
)


def build(horizon: int = HORIZON) -> tuple[list[Row], list[Refusal]]:
    """Every decision date in the overlap, split into what may be learned from and what may not.

    The frame is built over the days on which the exchange rate exists, because that is the
    shortest of the three series, and a decision date is only a decision date if every feature
    it needs could have been read that morning.
    """
    yields = corpus.fed("DGS10")
    slopes = corpus.fed("T10Y2Y")
    rates = corpus.fed("DEXUSEU")
    quarterly = corpus.fed("GDPC1")

    # WHEN EACH QUARTERLY FIGURE WAS ACTUALLY SERVED, recovered from the archive. The frame
    # cannot start before the first of these, because before it there is no honest answer to
    # what was knowable, and guessing one is the mistake this repository is about. That bound is
    # why the frame covers the recovered window rather than every day the yields exist.
    published = {
        datetime.date.fromisoformat(row["observation"]): datetime.date.fromisoformat(
            row["knowable_from"]
        )
        for row in corpus.knowable_from()
        if row["series"] == "GDPC1"
    }
    if not published:
        raise ValueError("no quarterly publication date was recovered, so no frame is honest")

    lag = datetime.timedelta(days=YIELD_RELEASE_LAG_DAYS)
    trading_days = sorted(set(yields) & set(slopes))
    position = {day: index for index, day in enumerate(trading_days)}

    rows: list[Row] = []
    refusals: list[Refusal] = []

    for decision_date in sorted(day for day in rates if day >= trading_days[0]):
        # The most recent yield the publisher had SERVED by this morning, which is not the same
        # as the most recent yield it is ABOUT. Reading the second is the leak.
        usable = [day for day in trading_days if day + lag <= decision_date]
        if not usable:
            refusals.append(
                Refusal(decision_date, REASONS[1], "no H.15 observation had been released yet")
            )
            continue
        latest = usable[-1]

        # The most recent quarterly figure SERVED by this morning, which is routinely two
        # quarters behind the one whose label has already passed.
        served = [label for label, when in published.items() if when <= decision_date]
        if not served:
            refusals.append(
                Refusal(
                    decision_date,
                    REASONS[2],
                    "no quarterly figure had been published yet at this date, and the archive "
                    "was only bisected back to the first one recovered",
                )
            )
            continue
        # THE TOP END OF THE RECOVERY IS NOT THE TOP END OF THE CORPUS. The refusal above covers
        # the start, where nothing had been recovered yet and there is no honest answer. There is
        # no matching refusal here, so past the last recovered quarter this keeps serving that
        # one. The corpus holds values for later quarters whose publication dates were never
        # bisected; which ones is pinned by a test and stated in the README, rather than being
        # absorbed into a feature nobody can see it in.
        newest = max(served)

        index = position[latest]
        outcome_index = index + horizon
        outcome_date: datetime.date | None = None
        outcome: int | None = None
        if outcome_index < len(trading_days):
            outcome_date = trading_days[outcome_index]
            # AND the outcome must have been PUBLISHED, not merely have happened. The last
            # observation in the corpus is knowable a day after the day it is about, so a
            # horizon ending on the final trading day is still not decidable today.
            if outcome_date + lag <= max(rates):
                outcome = int(yields[outcome_date] > yields[latest])

        if outcome is None:
            # Written as a plain concatenation because a line break inside an f-string
            # replacement field is Python 3.12 or newer, and this repository's floor is 3.11.
            where = outcome_date.isoformat() if outcome_date else "beyond the end of the corpus"
            refusals.append(
                Refusal(
                    decision_date,
                    REASONS[0],
                    f"the {horizon} day outcome falls on {where} and had not been published "
                    f"by the last day this corpus covers",
                )
            )
            continue

        rows.append(
            Row(
                decision_date=decision_date,
                latest_yield_date=latest,
                level=yields[latest],
                slope=slopes[latest],
                # THE UNMEASURED CLOCK. The module docstring says which series it is and why
                # it is still read at its own label date.
                fx=rates[decision_date],
                gdp=quarterly[newest],
                gdp_age_days=(decision_date - newest).days,
                outcome_date=outcome_date,
                outcome=outcome,
            )
        )

    return rows, refusals


def scoreable_and_labelled(horizon: int = HORIZON) -> tuple[int, int]:
    """The ratio the front page leads with, as two counts.

    Scoreable means a model could have run that morning. Labelled means the row may be learned
    from. The gap between them is not a data quality problem to be fixed: it is the set of days
    where a decision is possible and supervision is not, which is every day near the present.
    """
    rows, refusals = build(horizon)
    undecidable = sum(1 for refusal in refusals if refusal.reason == REASONS[0])
    return len(rows) + undecidable, len(rows)


@dataclass(frozen=True)
class LeakCount:
    """What reading a feature at its label date rather than its publication date costs."""

    decision_dates: int
    dates_reading_an_unpublished_figure: int
    worst_days_early: int
    naive_and_honest_differ_on: int

    @property
    def share(self) -> float:
        return self.dates_reading_an_unpublished_figure / self.decision_dates


def quarterly_leak(horizon: int = HORIZON) -> LeakCount:
    """Compare reading the quarterly series at its LABEL against reading it when it existed.

    The naive frame takes the most recent observation whose label is on or before the decision
    date. The honest frame takes the most recent observation the publisher had actually served
    by then, which is recovered per observation by bisecting the archive.

    THE LAG IS NOT A CONSTANT, which is the whole reason this cannot be a table. Across the 43
    quarters recovered, 41 were first published between 115 and 121 days after the day they are
    labelled, and two took 150 and 175. Nothing in the data says which, and a pipeline using an
    average would be wrong by a quarter twice in ten years and right the rest of the time, which
    is the pattern that survives review.
    """
    recovered = {
        (row["series"], row["observation"]): datetime.date.fromisoformat(row["knowable_from"])
        for row in corpus.knowable_from()
        if row["series"] == "GDPC1"
    }
    if not recovered:
        raise ValueError("no quarterly observation has a recovered publication date")

    labels = sorted(datetime.date.fromisoformat(observation) for _, observation in recovered)
    first_covered = min(recovered.values())

    rows, _ = build(horizon)
    considered = [row for row in rows if row.decision_date >= first_covered]

    early = 0
    worst = 0
    differ = 0
    for row in considered:
        naive = [label for label in labels if label <= row.decision_date]
        honest = [
            label
            for label in labels
            if recovered[("GDPC1", label.isoformat())] <= row.decision_date
        ]
        if not naive:
            continue
        if naive[-1] != (honest[-1] if honest else None):
            differ += 1
        published = recovered[("GDPC1", naive[-1].isoformat())]
        if published > row.decision_date:
            early += 1
            worst = max(worst, (published - row.decision_date).days)

    return LeakCount(
        decision_dates=len(considered),
        dates_reading_an_unpublished_figure=early,
        worst_days_early=worst,
        naive_and_honest_differ_on=differ,
    )
