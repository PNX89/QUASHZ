"""What a decision on one morning could honestly have used, printed from committed files.

    uv run python examples/what_was_knowable.py

NO INSTRUMENT, NO NETWORK, NO CREDENTIAL. The verdict needs scikit-learn, DuckDB and Soda, and
all three are worth running. None of them is worth requiring of somebody who has just cloned
this and wants to know what it is about, so this reads the committed corpus with the standard
library and shows the one thing the whole repository turns on: the gap between the day a number
is ABOUT and the day it could first be read.
"""

from __future__ import annotations

import datetime
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from quashz import corpus, frame

WHEN = datetime.date(2024, 4, 24)


def main() -> None:
    recovered = [row for row in corpus.knowable_from() if row["series"] == "GDPC1"]
    lags = sorted(int(row["days_from_the_observation_label"]) for row in recovered)

    print(
        f"{len(recovered)} quarterly publication dates recovered from the archive, "
        f"by bisection, never assumed."
    )
    print()
    print("How long after the day it is labelled each figure was first served:")
    print()
    ordinary = [lag for lag in lags if lag <= 130]
    print(f"  {len(ordinary)} of {len(lags)} between {min(ordinary)} and {max(ordinary)} days")
    for lag in lags:
        if lag > 130:
            row = next(r for r in recovered if int(r["days_from_the_observation_label"]) == lag)
            print(f"  and one at {lag} days: {row['observation']}, served {row['knowable_from']}")
    print()
    print("  A pipeline using the average of those would be right most of the time,")
    print("  and a quarter wrong twice in ten years.")
    print()

    print(f"Asked on {WHEN}, which quarterly figure could a decision have used?")
    print()
    for row in recovered:
        served = datetime.date.fromisoformat(row["knowable_from"])
        label = datetime.date.fromisoformat(row["observation"])
        if abs((served - WHEN).days) <= 2 or (label.year, label.month) == (2024, 1):
            state = "already served" if served <= WHEN else f"NOT UNTIL {served}"
            print(f"  the quarter labelled {row['observation']}   {state}")
    print()
    print("  Reading it by its label would have used a number that did not exist for")
    print("  another day. That is one row. Measured across the whole frame:")
    print()

    leak = frame.quarterly_leak()
    print(
        f"  {leak.dates_reading_an_unpublished_figure} of {leak.decision_dates} decision dates "
        f"({leak.share:.1%}) would read a figure"
    )
    print(f"  the publisher had not published, by up to {leak.worst_days_early} days.")
    print()

    rows, refusals = frame.build()
    scoreable, labelled = frame.scoreable_and_labelled()
    print("And what the frame does about it:")
    print()
    print(f"  {scoreable} days a model could have run on")
    print(f"  {labelled} days it could have learned from")
    print(f"  {scoreable - labelled} days where a decision is possible and supervision is not")
    print()
    print("  The last figure is not a defect to be fixed. It is every day near the present.")
    print()
    example = rows[-1]
    print(f"  The last row admitted is {example.decision_date}, deciding on a yield published")
    print(f"  {example.latest_yield_date} and judged on an outcome dated {example.outcome_date}.")

    # THE AGE IS BOUNDED BY THIS CAPTURE RATHER THAN BY THE PUBLISHER. Printed bare, it read as
    # a fact about the statistical office, on a page that opens by saying the ordinary lag is
    # about four months. It is not: the bisection stops at the last quarter it recovered, and
    # every decision date after that keeps reading the same figure while the age climbs.
    newest = max(datetime.date.fromisoformat(row["observation"]) for row in recovered)
    unrecovered = sorted(label for label in corpus.fed("GDPC1") if label > newest)
    print(f"  The quarterly figure it may read is already {example.gdp_age_days} days old,")
    print("  which is the reach of this bisection rather than the publisher's cadence: it")
    print(f"  was run forward only to the quarter labelled {newest}, and the corpus holds")
    print(f"  {len(unrecovered)} later quarters whose publication dates were never recovered.")
    print()

    # THE FIRST REFUSAL AFTER THE LAST ADMISSION, which is what the sentence says. This was
    # `max` over the whole ledger, so it printed the LAST refused date in the corpus, a month
    # past the boundary rather than the day after it. The exhibit closes on the moment
    # supervision runs out, and a date a month further on shows nothing of the sort.
    following = min(
        refusal.decision_date
        for refusal in refusals
        if refusal.decision_date > example.decision_date
    )
    print(f"  The first row refused after it is {following}, and the reason is not that a")
    print("  column was null. It is that the answer had not happened yet.")


if __name__ == "__main__":
    main()
