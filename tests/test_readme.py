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

import json
import pathlib
import re
from typing import Any

import pytest
import yaml

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
    """NUMBER, as a table of claim against source, so an unedited neighbour is visible."""
    verdict = evidence("verdict")
    reconciliation = evidence("reconciliation")
    contract = evidence("contract")

    claims = {
        "rows admitted": f"{verdict['admitted']:,}",
        "rows refused": f"{verdict['refused']:,}",
        "effective observations": str(verdict["verdicts"][0]["effective_observations"]),
        "ensemble": str(verdict["ensemble"]),
        "days both publish the rate": str(reconciliation["fx"]["days_both_publish"]),
        "days they agree exactly": str(reconciliation["fx"]["agree_exactly"]),
        "largest fx difference": str(reconciliation["fx"]["largest_difference"]),
        "days the identity holds": f"{reconciliation['identity']['days_it_holds']:,}",
        "days it fails": str(reconciliation["identity"]["days_it_fails"]),
        "checks in the contract": str(contract["checks_in_the_contract"]),
    }
    missing = {name: value for name, value in claims.items() if value not in README}
    assert missing == {}, f"the README no longer states these measured figures: {missing}"


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
