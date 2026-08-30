"""Every checkable claim on the front page, checked, and written before the page existed.

Four kinds of claim, following the contract this toolset shares:

    NUMBER     a figure on the page against the measurement that produced it
    COMMAND    a command the page offers against what CI actually runs
    OUTPUT     a quoted block, line by line, against the transcript it names
    REFERENCE  every link and path against what exists

Plus the one this repository needs and the others do not: a VOCABULARY check. Every claim here
is bounded, and a page that says a rule prevents or eliminates anything has stopped describing
what was measured.
"""

from __future__ import annotations

import datetime
import json
import pathlib
import re
from typing import Any

import pytest
import yaml

from quashz import corpus, frame

REPO = pathlib.Path(__file__).resolve().parents[1]
README = (REPO / "README.md").read_text(encoding="utf-8")
EVIDENCE = REPO / "docs" / "evidence"


def evidence(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(
        (EVIDENCE / name / "summary.json").read_text(encoding="utf-8")
    )
    return loaded


def own_prose() -> str:
    """The page minus the generated cross-link footer, which describes other repositories."""
    start, end = "<!-- toolset:start -->", "<!-- toolset:end -->"
    if start in README and end in README:
        return README[: README.index(start)] + README[README.index(end) + len(end) :]
    return README


def test_the_numbers_on_the_page_are_the_measured_ones() -> None:
    """NUMBER, as a table of claim against source, each figure anchored to its own sentence.

    THE FIGURE IS CHECKED IN THE SENTENCE THAT CARRIES IT. This asked whether each value was a
    substring of the page, and three of these claims are one or two characters long, so they
    were satisfied by a digit somewhere in twelve kilobytes of prose whatever the page said.
    Changing "5 checks pass" to "97 checks pass" and the identity's "fails on **3**" to "**7**"
    left the whole suite green.

    The overcorrection is worth naming too, because it is the same defect facing the other way:
    an anchor demanding a whole sentence goes red the day the page is legitimately rewritten and
    teaches the next person to loosen it. Each pattern here is the figure plus the few words
    that make it mean something, and nothing more.
    """
    verdict = evidence("verdict")
    reconciliation = evidence("reconciliation")
    contract = evidence("contract")
    lags = sorted(
        int(row["days_from_the_observation_label"])
        for row in corpus.knowable_from()
        if row["series"] == "GDPC1"
    )
    ordinary = [lag for lag in lags if lag <= 130]
    unusual = sorted(set(lags) - set(ordinary))
    quarterly_probes = sum(
        int(row["probes"]) for row in corpus.knowable_from() if row["series"] == "GDPC1"
    )
    daily_probes = sum(
        int(row["probes"]) for row in corpus.knowable_from() if row["series"] != "GDPC1"
    )
    rows, _ = frame.build()
    held = [label for label in corpus.fed("GDPC1") if label >= datetime.date(2015, 1, 1)]
    newest = max(
        datetime.date.fromisoformat(row["observation"])
        for row in corpus.knowable_from()
        if row["series"] == "GDPC1"
    )
    leak = frame.quarterly_leak()
    # The two figures with a decimal point in them are escaped, because an unescaped point
    # matches any character and an anchor that accepts 94x8 is looser than it looks.
    largest = re.escape(str(reconciliation["fx"]["largest_difference"]))
    share = re.escape(f"{leak.share * 100:.1f}")
    # HOW FAR EACH OF THE THREE IDENTITY FAILURES MISSES BY, not just how many there are. A page
    # that says "each off by two hundredths" when one of the three misses by one hundredth is
    # wrong about the exhibit's own load-bearing number, and the count check above does not
    # catch it because it never looks at the magnitudes.
    places = reconciliation["identity"]["places"]
    failure_sizes = sorted(
        round(abs(entry["published"] - entry["difference"]), places)
        for entry in reconciliation["identity"]["the_failures"]
    )
    single = re.escape(str(failure_sizes[0]))
    paired = re.escape(str(failure_sizes[-1]))

    # THE PAGE IS FLATTENED FIRST, because a sentence on this page is wrapped at a hundred
    # characters and an anchor that cannot cross a line break is an anchor that fails the day
    # somebody rewraps a paragraph. The figures and the words either side of them survive
    # rewrapping; the line breaks between them do not.
    flattened = " ".join(README.split())

    claims = {
        "rows admitted": rf"{verdict['admitted']:,} rows at a twenty day horizon",
        "rows refused": rf"Of the {verdict['refused']:,} rows refused",
        "effective observations": (
            rf"are {verdict['verdicts'][0]['effective_observations']} effectively independent"
        ),
        "ensemble": rf"permuted {verdict['ensemble']} times",
        "days both publish the rate": (
            rf"days both publish\s+{reconciliation['fx']['days_both_publish']}\b"
        ),
        "days they agree exactly": (
            rf"days they agree exactly\s+{reconciliation['fx']['agree_exactly']}\b"
        ),
        "largest fx difference": (rf"largest difference\s+{largest}\b"),
        "days all three series exist": (
            rf"Over {reconciliation['identity']['days_all_three_exist']:,} days"
        ),
        "days the identity holds": (
            rf"it holds on \*\*{reconciliation['identity']['days_it_holds']:,}\*\*"
        ),
        "days it fails": rf"fails on \*\*{reconciliation['identity']['days_it_fails']}\*\*",
        "the size of the three identity failures": (
            rf"two of them by {paired} and the third by {single}"
        ),
        "checks in the contract": (
            rf"{contract['checks_in_the_contract']} checks pass on the admitted frame"
        ),
        "probes spent bisecting": rf"{quarterly_probes + daily_probes} probes in all",
        "probes spent on the quarters": rf"{quarterly_probes} across the {len(lags)} quarters",
        "probes spent on the daily checks": rf"{daily_probes} on two spot checks",
        "quarters in the ordinary band": rf"{len(ordinary)} of the {len(lags)} quarters",
        "the ordinary band itself": rf"between {min(ordinary)} and {max(ordinary)} days",
        "the two that took longer": rf"two took {unusual[0]} and {unusual[1]}",
        "quarters the bisection reached": rf"reached {len(lags)} of the {len(held)} quarters",
        "the last quarter it reached": rf"labelled {newest}",
        "the age at the end of the frame": rf"climbs to {rows[-1].gdp_age_days} days",
        "dates reading an unpublished figure": (
            rf"on {leak.dates_reading_an_unpublished_figure:,} of the {leak.decision_dates:,} "
            rf"decision dates, {share} per cent"
        ),
        "the worst it reads early by": rf"by up to {leak.worst_days_early} days",
    }
    missing = {
        name: pattern for name, pattern in claims.items() if not re.search(pattern, flattened)
    }
    assert missing == {}, (
        f"the README no longer states these measured figures in the sentences that carry them: "
        f"{missing}"
    )


def test_the_two_estimator_results_are_both_on_the_page() -> None:
    """NUMBER. Reporting one family and calling it the answer is the failure being guarded."""
    for entry in evidence("verdict")["verdicts"]:
        assert entry["estimator"] in README, f"{entry['estimator']} is not named"
        assert f"{entry['observed_auc']:.4f}" in README, (
            f"the page does not state {entry['estimator']}'s score of {entry['observed_auc']:.4f}"
        )
        mde = entry["minimum_detectable_effect"]
        assert mde is None or str(mde) in README


def test_no_large_number_on_the_page_is_one_nothing_measured() -> None:
    """The half `in README` cannot do: a stale copy of a figure elsewhere on the page."""
    verdict = evidence("verdict")
    reconciliation = evidence("reconciliation")
    measured: set[int] = {
        verdict["admitted"],
        verdict["refused"],
        verdict["ensemble"],
        reconciliation["identity"]["days_all_three_exist"],
        reconciliation["identity"]["days_it_holds"],
    }
    for entry in verdict["verdicts"]:
        measured.update({entry["observations"], entry["effective_observations"]})
    from quashz import corpus, frame

    scoreable, labelled = frame.scoreable_and_labelled()
    leak = frame.quarterly_leak()
    measured.update({entry["rows"] for entry in verdict["refusals_by_reason"]})
    measured.update(
        {
            scoreable,
            labelled,
            leak.decision_dates,
            leak.dates_reading_an_unpublished_figure,
            len(corpus.knowable_from()),
        }
    )
    written = {
        int(token.replace(",", "")) for token in re.findall(r"\b\d{1,3}(?:,\d{3})+\b", README)
    }
    invented = sorted(written - measured)
    assert invented == [], (
        f"the page states {invented}, and nothing under docs/evidence or in the corpus produces "
        f"those figures"
    )


def test_every_command_the_page_offers_is_one_ci_runs() -> None:
    """COMMAND. Except the three that run inside the shared workflow, which is named."""
    workflow = yaml.safe_load((REPO / ".github" / "workflows" / "ci.yml").read_text("utf-8"))
    executed = "\n".join(
        line
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
        if isinstance(step.get("run"), str)
        for line in step["run"].splitlines()
        if not line.strip().startswith("#")
    )
    shared = "PNX89/.github/.github/workflows/checks.yml"
    assert shared in (REPO / ".github" / "workflows" / "ci.yml").read_text("utf-8")
    delegated = ("uv run pytest", "uv run ruff", "uv run mypy", "uv sync")

    offered = re.findall(r"^\s*(?:\$ )?(uv run [^\n]+|scripts/\S+)$", README, re.MULTILINE)
    assert offered, "the README offers no command at all"
    for command in offered:
        command = command.strip()
        if command.startswith(delegated):
            continue
        assert command in executed, f"the README offers `{command}` and CI never runs it"


def test_every_block_quoted_from_a_transcript_is_in_that_transcript() -> None:
    """OUTPUT, line by line, against the file each block names in an HTML comment."""
    blocks = re.findall(r"<!-- quoted from (\S+) -->\n```text\n(.*?)```", README, re.S)
    assert blocks, "no block on the page declares where it was quoted from"
    for path, body in blocks:
        source = REPO / path
        assert source.exists(), f"the page quotes {path}, which does not exist"
        lines = {line.strip() for line in source.read_text("utf-8").splitlines()}
        for line in body.splitlines():
            if line.strip():
                assert line.strip() in lines, (
                    f"the page quotes {line.strip()!r} as coming from {path}, and it is not there"
                )


def test_every_path_and_link_on_the_page_exists() -> None:
    """REFERENCE, including the paths written as inline code."""
    targets = set(re.findall(r"\]\((?!https?:)([^)#]+)", README))
    targets |= {
        found
        for found in re.findall(r"`([a-zA-Z0-9_./-]+)`", README)
        if "/" in found and not found.startswith(("http", "-"))
    }
    missing = sorted(target for target in targets if not (REPO / target.strip()).exists())
    assert missing == [], f"the README points at paths that do not exist: {missing}"


@pytest.mark.parametrize(
    "banned",
    [
        "prevents",
        "guarantees",
        "eliminates",
        "solves",
        "blocks all",
        "no leakage",
        "leakage",
        "overfitting",
        "out-of-sample",
        "walk-forward",
        "position sizing",
        "sharpe",
        "our model predicts",
        "trading signal",
    ],
)
def test_the_page_avoids_the_vocabulary_that_claims_more_than_was_measured(banned: str) -> None:
    """Every result here is bounded by a procedure on one frame, and the words follow.

    Some of these are banned because they overclaim and some because they are the vocabulary of
    a different job. A page that reaches for either is describing something other than what the
    harnesses in this repository actually ran.
    """
    assert banned not in own_prose().lower()


def test_the_page_states_what_the_controls_do_not_establish() -> None:
    """The sentence that has to be there, not merely the absence of the ones that must not."""
    flattened = " ".join(own_prose().split()).lower()
    assert "could have detected" in flattened
    assert "not a multiple comparisons correction" in flattened or (
        "corrects for no multiple comparison" in flattened
    )
