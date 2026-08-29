"""The refusals, joined to the archive that measured them rather than to a constant.

The frame uses a one day release lag for the H.15 yields. That number is not a convention and it
is not in the data: it was recovered by bisecting ALFRED vintages, and the first test here joins
the constant in the code to the file that measured it. A lag hard-coded and separately correct
is the shape of defect this whole repository is about.
"""

from __future__ import annotations

import csv
import datetime

from quashz import corpus, frame


def test_the_release_lag_in_the_code_is_the_one_the_archive_measured() -> None:
    """THE JOIN. Otherwise the constant and the measurement drift apart in silence."""
    daily = [row for row in corpus.knowable_from() if row["series"] == "DGS10"]
    assert daily, "the archive recovered no daily observation, so the lag rests on nothing"
    measured = {int(row["days_from_the_observation_label"]) for row in daily}
    assert measured == {frame.YIELD_RELEASE_LAG_DAYS}, (
        f"the archive measured lags of {sorted(measured)} days for the daily series and the "
        f"frame uses {frame.YIELD_RELEASE_LAG_DAYS}"
    )


def test_the_quarterly_series_is_published_months_after_the_period_it_names() -> None:
    """The fact the front page leads with, taken from the recovered dates rather than asserted."""
    quarterly = [row for row in corpus.knowable_from() if row["series"] == "GDPC1"]
    assert quarterly, "no quarterly observation was recovered"
    lags = [int(row["days_from_the_observation_label"]) for row in quarterly]
    assert min(lags) > 90, (
        f"the smallest recovered publication lag is {min(lags)} days, so the claim that this "
        f"series is published months after the period it names no longer holds"
    )
    assert len(set(lags)) > 1, (
        "every recovered lag is identical, which would mean a constant would have done and the "
        "bisection bought nothing. Check the recovery before relaxing this"
    )


def test_no_admitted_row_reads_a_number_that_had_not_been_published() -> None:
    """The leak test, and the one that has to survive being attacked.

    Every admitted row is checked against the same rule the archive measured: the observation it
    reads must have been SERVED before the morning the decision is made on. Reading the same
    day's yield is the ordinary version of this mistake and it would leave every other test here
    passing.
    """
    rows, _ = frame.build()
    lag = datetime.timedelta(days=frame.YIELD_RELEASE_LAG_DAYS)
    offenders = [row for row in rows if row.latest_yield_date + lag > row.decision_date]
    assert offenders == [], (
        f"{len(offenders)} rows read an observation that had not been published by their own "
        f"decision date, the first on {offenders[0].decision_date}"
    )


def test_every_admitted_row_has_an_outcome_that_had_already_happened() -> None:
    """The other direction of the same clock."""
    rows, _ = frame.build()
    for row in rows:
        assert row.outcome_date is not None
        assert row.outcome_date > row.latest_yield_date, (
            f"the outcome for {row.decision_date} is dated on or before the observation it is "
            f"measured from, so the horizon is not in front of the decision"
        )


def test_the_only_refusals_are_the_ones_the_horizon_makes_inevitable() -> None:
    """A refusal count that is not explained by the horizon is a refusal nobody has looked at."""
    rows, refusals = frame.build()
    assert refusals, "nothing was refused at all, so the ledger has nothing in it to argue with"
    reasons = {refusal.reason for refusal in refusals}
    assert reasons == {frame.REASONS[0]}, f"an unexplained refusal reason appeared: {reasons}"
    assert len(refusals) <= frame.HORIZON + 2, (
        f"{len(refusals)} rows were refused for an undecidable outcome, which is more than a "
        f"{frame.HORIZON} day horizon at the end of the corpus can account for"
    )
    assert all(refusal.decision_date > rows[-1].decision_date for refusal in refusals), (
        "a row in the middle of the corpus was refused for an undecidable outcome, which means "
        "the trading day index has a hole in it rather than that the horizon ran out"
    )


def test_the_scoreable_and_labelled_counts_differ_by_exactly_the_refusals() -> None:
    """The ratio the front page states, checked as arithmetic rather than quoted."""
    scoreable, labelled = frame.scoreable_and_labelled()
    rows, refusals = frame.build()
    assert labelled == len(rows)
    assert scoreable - labelled == len(refusals)
    assert 0 < labelled < scoreable, (
        "every scoreable row is labelled, so there is no gap between what can be decided and "
        "what can be learned from, and the front page has nothing to show"
    )


def test_the_ecb_file_is_committed_exactly_as_the_publisher_served_it() -> None:
    """The licence constraint, as a check rather than as a promise in a docstring.

    The ECB permits reuse without modification only, metadata included. A tidied two-column file
    would be a modification, so all 32 columns are here and this fails if somebody helpfully
    prunes them.
    """
    path = corpus.DATA / "ECB_EXR_D_USD_EUR_SP00_A.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        fields = csv.DictReader(handle).fieldnames or []
    assert len(fields) >= 30, (
        f"the ECB file now has {len(fields)} columns. It is redistributed under terms that "
        f"permit no modification of the data OR the metadata, so pruning it is not tidying"
    )
    for expected in ("KEY", "TIME_PERIOD", "OBS_VALUE", "TITLE_COMPL", "SOURCE_AGENCY"):
        assert expected in fields, f"{expected} is missing, so the file has been edited"


def test_a_publisher_holiday_is_a_day_with_no_number_rather_than_a_null() -> None:
    """Filling a holiday forward invents an observation the publisher never made."""
    values = corpus.fed("DGS10")
    assert datetime.date(2024, 1, 1) not in values, (
        "New Year's Day carries a yield, so the missing marker is being read as a value"
    )
    assert datetime.date(2024, 1, 2) in values


def test_an_outcome_that_happened_is_not_enough_if_it_was_not_published() -> None:
    """THE DISTINCTION A MUTATION FOUND UNGUARDED, and it is one row wide.

    An outcome twenty trading days after the decision has HAPPENED once that day arrives. It has
    not been PUBLISHED until the release lag has run, which for this series is the following
    day. Dropping that second condition changes exactly one row at the end of the corpus and no
    other test here noticed, which is how a one row leak survives a green suite.

    The rule: every admitted outcome must have been served by the last day this corpus can see.
    """
    rows, _ = frame.build()
    lag = datetime.timedelta(days=frame.YIELD_RELEASE_LAG_DAYS)
    latest_visible = max(corpus.fed("DEXUSEU"))
    late = [row for row in rows if row.outcome_date and row.outcome_date + lag > latest_visible]
    assert late == [], (
        f"{len(late)} admitted rows carry an outcome whose publication falls after "
        f"{latest_visible}, the last day this corpus covers. The first is "
        f"{late[0].decision_date} with an outcome dated {late[0].outcome_date}"
    )


def test_reading_a_quarterly_figure_at_its_label_date_is_measured_rather_than_warned_about() -> (
    None
):
    """The exhibit, as arithmetic. Every number here is recomputed from the recovered dates."""
    leak = frame.quarterly_leak()
    assert leak.decision_dates > 1000, "the comparison covers too little to say anything"
    assert leak.dates_reading_an_unpublished_figure > 0
    assert leak.share > 0.5, (
        f"only {leak.share:.1%} of decision dates would read an unpublished figure, so the "
        f"exhibit no longer shows what it claims"
    )
    assert leak.worst_days_early >= 115, (
        "the worst case is under the smallest publication lag in the archive, which cannot "
        "happen unless the comparison is measuring something else"
    )
    assert leak.naive_and_honest_differ_on >= leak.dates_reading_an_unpublished_figure, (
        "the two frames disagree on fewer dates than the naive one reads an unpublished figure "
        "on, which is arithmetically impossible"
    )


def test_the_publication_lag_is_not_a_constant_and_the_outliers_are_kept() -> None:
    """Why this is a bisection and not a table.

    41 of the 43 recovered quarters were first served between 115 and 121 days after the day
    they are labelled. Two took 150 and 175. This repository does not assert why, because that
    would be a claim about a publisher's operations rather than a measurement, and the archive
    records when rather than why. What it does assert is the spread, because a mean of these
    would be right most of the time and a quarter wrong twice in ten years.
    """
    lags = sorted(
        int(row["days_from_the_observation_label"])
        for row in corpus.knowable_from()
        if row["series"] == "GDPC1"
    )
    assert len(lags) >= 40, f"only {len(lags)} quarters were recovered"
    assert max(lags) - min(lags) > 40, (
        f"the recovered lags span {max(lags) - min(lags)} days, so a constant would have done "
        f"and the bisection bought nothing"
    )
    typical = [lag for lag in lags if lag <= 130]
    assert len(typical) >= len(lags) - 4, "more than a handful of quarters are far from the rest"
    assert max(typical) - min(typical) <= 15, (
        "even the ordinary quarters vary by more than a fortnight, which is worth reading about "
        "before this is described as a narrow band"
    )


def test_every_recovered_bracket_crossed_a_real_publication() -> None:
    """The content hash check, verified on the committed result rather than only at capture time.

    The archive answers HTTP 200 for a calendar date that is not a vintage, serving the nearest
    preceding one under a header echoing the date asked for. Two adjacent probes returning
    identical data therefore prove nothing happened between them, and a boundary reported there
    would be an artefact of the endpoint.
    """
    rows = corpus.knowable_from()
    assert rows
    for row in rows:
        assert row["rows_digest_when_absent"] != row["rows_digest_when_present"], (
            f"{row['series']} {row['observation']}: the probes either side of "
            f"{row['knowable_from']} returned identical data, so no publication happened between "
            f"them and the recovered date is an artefact"
        )
        assert len(row["rows_digest_when_present"]) == 64, "that is not a SHA-256"
        assert row["last_probe_without_it"] < row["knowable_from"]
