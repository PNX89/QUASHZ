"""The refusals, joined to the archive that measured them rather than to a constant.

The frame uses a one day release lag for the H.15 yields. That number is not a convention and it
is not in the data: it was recovered by bisecting ALFRED vintages, and the first test here joins
the constant in the code to the file that measured it. A lag hard-coded and separately correct
is the shape of defect this whole repository is about.
"""

from __future__ import annotations

import csv
import datetime
import pathlib

from quashz import corpus, frame

#: The demo's captured stdout. CI re-runs the demo and fails if a byte of this moved, so a claim
#: asserted against this file is a claim asserted against what the demo prints.
DEMO = pathlib.Path(__file__).resolve().parents[1] / "docs" / "evidence" / "demo.txt"


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


def test_every_refusal_is_explained_by_one_of_the_two_boundaries() -> None:
    """A refusal nobody can account for is a refusal nobody has looked at.

    There are exactly two boundaries here and they sit at opposite ends of the corpus. At the
    START, no quarterly figure had been published yet at a date the archive covers, because the
    bisection was only run back to 2015 and inventing an earlier publication date is the mistake
    this repository exists to refuse. At the END, the outcome has not happened yet.
    """
    rows, refusals = frame.build()
    assert refusals, "nothing was refused at all, so the ledger has nothing in it to argue with"
    reasons = {refusal.reason for refusal in refusals}
    assert reasons == {frame.REASONS[0], frame.REASONS[2]}, (
        f"an unexplained refusal reason appeared: {reasons}"
    )

    undecidable = [r for r in refusals if r.reason == frame.REASONS[0]]
    unpublished = [r for r in refusals if r.reason == frame.REASONS[2]]
    assert len(undecidable) <= frame.HORIZON + 2, (
        f"{len(undecidable)} rows were refused for an undecidable outcome, which is more than a "
        f"{frame.HORIZON} day horizon at the end of the corpus can account for"
    )
    assert all(r.decision_date > rows[-1].decision_date for r in undecidable), (
        "a row in the middle of the corpus was refused for an undecidable outcome, which means "
        "the trading day index has a hole in it rather than that the horizon ran out"
    )
    assert all(r.decision_date < rows[0].decision_date for r in unpublished), (
        "a row inside the recovered window was refused for want of a published figure, so the "
        "archive has a gap in the middle rather than a start"
    )


def test_the_scoreable_and_labelled_counts_differ_by_exactly_the_undecidable_rows() -> None:
    """The ratio the front page states, checked as arithmetic rather than quoted.

    SCOREABLE counts the rows a model could have RUN on: every feature was published in time.
    LABELLED counts the rows it could have LEARNED from: the outcome had happened and been
    published too. The gap between them is not a data quality problem to be fixed. It is the set
    of days where a decision is possible and supervision is not, which is every day near the
    present, and the rows refused for want of a published feature are in NEITHER count because a
    model could not have run on them either.
    """
    scoreable, labelled = frame.scoreable_and_labelled()
    rows, refusals = frame.build()
    undecidable = [r for r in refusals if r.reason == frame.REASONS[0]]
    assert labelled == len(rows)
    assert scoreable - labelled == len(undecidable)
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


def test_the_exchange_rate_is_the_one_feature_read_at_its_own_label_date() -> None:
    """THE THIRD CLOCK, WHICH NOTHING READ. Asserted because it is a departure, not a detail.

    The yields are read at the lag the archive measured for DGS10. The exchange rate is not: no
    DEXUSEU observation was ever bisected, so `fx` is taken from the observation labelled the
    decision date itself, on a lag nothing here measured. SOURCE.json calls it a noon buying
    rate, and a noon rate is not knowable on the morning of the same day.

    The test above checks `latest_yield_date` and nothing else, so pointing `fx` at TOMORROW's
    rate, which is an unambiguous look-ahead, left both suites green. This pins the clock the
    frame actually uses, in both directions: recovering DEXUSEU's publication dates and applying
    them is what closes it, and that moves every measured number reading this frame, so it fails
    here first rather than arriving inside a regenerated verdict.
    """
    rows, _ = frame.build()
    rates = corpus.fed("DEXUSEU")
    measured = {row["series"] for row in corpus.knowable_from()}
    assert "DEXUSEU" not in measured, (
        "DEXUSEU now has a recovered publication date, so the frame can read the rate the "
        "publisher had SERVED rather than the one labelled the decision date. Apply it in "
        "build() and replace this test rather than relaxing it"
    )
    offenders = [row for row in rows if row.fx != rates[row.decision_date]]
    assert offenders == [], (
        f"{len(offenders)} rows read an exchange rate that is not the one labelled their own "
        f"decision date, the first on {offenders[0].decision_date}. That is a change to the "
        f"third clock, and every measured number that reads this frame moves with it"
    )


def test_the_quarters_the_bisection_never_reached_are_named_rather_than_missing() -> None:
    """The recovery stops short of the corpus, and this is where that is written down.

    `knowable_from.csv` carries a publication date for every quarter the archive was bisected
    for, and the corpus carries VALUES for three quarters past the last of them. Nothing joined
    the two coverages, so the gap was invisible: `build()` serves the last recovered figure to
    every later decision date and `gdp_age_days` climbs to nearly twice any age the archive
    measured, which is a fact about this capture rather than about the publisher.

    PINNED BY NAME AND BY SIZE. A test asserting merely that some quarters are missing would
    pass with a fourth one gone; a test asserting a count would pass with a different three.
    Closing the gap is a `capture_knowable.py` run, which rewrites the corpus and every measured
    number that depends on it, so it is a deliberate act rather than a tidy-up and this goes red
    until somebody does it or edits this list on purpose.
    """
    recovered = {
        datetime.date.fromisoformat(row["observation"])
        for row in corpus.knowable_from()
        if row["series"] == "GDPC1"
    }
    held = [label for label in corpus.fed("GDPC1") if label >= datetime.date(2015, 1, 1)]
    uncovered = sorted(label.isoformat() for label in held if label not in recovered)
    assert uncovered == ["2025-10-01", "2026-01-01", "2026-04-01"], (
        f"the quarters this corpus holds a value for and the bisection never reached are now "
        f"{uncovered}. Re-run scripts/capture_knowable.py and regenerate every measurement that "
        f"reads the frame, or change this list on purpose"
    )
    assert max(recovered) < min(datetime.date.fromisoformat(label) for label in uncovered), (
        "an unrecovered quarter sits inside the recovered range, so this is a hole in the middle "
        "of the archive rather than a capture that stopped early"
    )


def test_the_demo_closes_on_the_first_refusal_after_the_last_admitted_row() -> None:
    """The sentence says FIRST and the arithmetic behind it took a maximum.

    A maximum over the whole ledger returns the last refused date in the corpus, which is a
    month past the boundary this exhibit is about. Nothing joined that line to anything, so a
    figure computed as the wrong quantity was published in the transcript, on the card and in
    the README's hero image, with every drift guard in the repository faithfully protecting it.

    Asserted against the sentence that carries it rather than against the file, because a
    thirty-five line transcript contains most of these dates somewhere.
    """
    rows, refusals = frame.build()
    last = rows[-1].decision_date
    following = sorted(r.decision_date for r in refusals if r.decision_date > last)
    assert following, "nothing is refused after the last admitted row, so the exhibit has no end"
    sentence = next(
        line
        for line in DEMO.read_text(encoding="utf-8").splitlines()
        if "The first row refused after it is" in line
    )
    assert following[0].isoformat() in sentence, (
        f"the demo closes on {sentence.strip()!r}, and the first row refused after {last} is "
        f"{following[0]}"
    )
    considered = sorted({r.decision_date for r in rows} | {r.decision_date for r in refusals})
    assert considered[considered.index(last) + 1] == following[0], (
        "the date the demo closes on is not the next decision date after the last admitted one, "
        "so the sentence is not describing the boundary it claims to describe"
    )


def test_the_demo_states_the_reach_of_the_bisection_beside_the_age_it_prints() -> None:
    """The age this exhibit closes on is bounded by the capture, not by the publisher.

    `gdp_age_days` is a model feature, and the transcript prints its largest value eleven lines
    under a line saying the ordinary publication lag is about four months. The number is
    correct; what makes it honest is the sentence around it, so the sentence is what is checked.
    """
    demo = DEMO.read_text(encoding="utf-8").splitlines()
    rows, _ = frame.build()
    newest = max(
        datetime.date.fromisoformat(row["observation"])
        for row in corpus.knowable_from()
        if row["series"] == "GDPC1"
    )
    unrecovered = sorted(label for label in corpus.fed("GDPC1") if label > newest)
    assert unrecovered, (
        "the corpus holds no quarter past the last recovered one, so this caveat describes "
        "nothing and should be deleted along with the lines it explains"
    )
    age = next(line for line in demo if "days old" in line)
    assert f"{rows[-1].gdp_age_days} days old" in age, (
        f"the demo prints {age.strip()!r} and the last admitted row's figure is "
        f"{rows[-1].gdp_age_days} days old"
    )
    reach = next(line for line in demo if "run forward only to" in line)
    assert newest.isoformat() in reach, (
        f"the demo says {reach.strip()!r} and the bisection was run forward to {newest}"
    )
    tail = next(line for line in demo if "later quarters" in line)
    assert tail.strip().startswith(f"{len(unrecovered)} later quarters"), (
        f"the demo says {tail.strip()!r} and {len(unrecovered)} quarters were never recovered"
    )
