"""What the verdict recorded, read offline, and checked for the ways a control can be hollow.

These read committed JSON and need none of the instruments, which is why they live in the
offline suite. What they defend is not "the numbers are good": it is that the controls were
capable of failing, that the null was built where it could bite, and that nothing here says
more than a bounded procedure on one frame can support.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[1]
EVIDENCE = REPO / "docs" / "evidence" / "verdict"


def summary() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((EVIDENCE / "summary.json").read_text(encoding="utf-8"))
    return loaded


def transcript() -> str:
    return (EVIDENCE / "the-verdict.txt").read_text(encoding="utf-8")


def test_the_rejection_rate_is_reported_with_its_reasons_and_they_add_up() -> None:
    """A bare rate hides which rule fired, and reasons that do not sum are two measurements."""
    numbers = summary()
    counted = sum(entry["rows"] for entry in numbers["refusals_by_reason"])
    assert counted == numbers["refused"], (
        f"the reasons account for {counted} refusals and the total says {numbers['refused']}"
    )
    considered = numbers["admitted"] + numbers["refused"]
    # The recorded rate is rounded to six places, so the tolerance is a rounding tolerance
    # rather than a float one. Asserting exact equality against a rounded field is a test that
    # fails for a reason that is not a defect.
    assert abs(numbers["rejection_rate"] - numbers["refused"] / considered) < 1e-6, (
        "the rejection rate is not the refusals over everything considered, so its denominator "
        "excludes something"
    )
    assert len(numbers["refusals_by_reason"]) >= 2, (
        "only one rule ever fires, so the ledger cannot show a reviewer which one caught a row"
    )


def test_the_null_was_built_where_it_could_actually_bite() -> None:
    """The check that separates a null from a formality.

    A permutation null whose maximum never comes near the observed score was built on a problem
    where nothing could go wrong. What is asserted is that the null has spread, that it is
    centred where a null should be, and that its upper tail reaches into the range the observed
    scores live in.
    """
    for entry in summary()["verdicts"]:
        assert entry["ensemble_size"] >= 50, "an ensemble this small cannot locate a rank"
        assert 0.45 <= entry["null_median"] <= 0.55, (
            f"{entry['estimator']}: the null sits at {entry['null_median']}, and a permuted "
            f"target should score about a half. A null that is off centre is measuring something"
        )
        assert entry["null_max"] > 0.55, (
            f"{entry['estimator']}: the null never exceeds {entry['null_max']}, so no "
            f"permutation ever looked like a finding and the comparison was never tested"
        )


def test_the_positive_control_is_a_sweep_that_fails_at_the_bottom_and_works_at_the_top() -> None:
    """A control that detects everything, or nothing, has measured nothing.

    The curve has to rise: it must miss the smallest planted effects and catch the largest, or
    the procedure's sensitivity has not been located and the minimum detectable effect is an
    artefact of where the grid happened to start.
    """
    for entry in summary()["verdicts"]:
        rates = entry["detection_rates"]
        effects = entry["detection_effects"]
        assert len(rates) == len(effects) >= 4, "the grid is too short to locate a boundary"
        assert min(rates) == 0.0, (
            f"{entry['estimator']}: even the smallest planted effect was detected, so the sweep "
            f"never found the bottom of this procedure's range and the reported minimum is just "
            f"the smallest number tried"
        )
        assert max(rates) >= 0.95, (
            f"{entry['estimator']}: even the largest planted effect was missed, so the procedure "
            f"was never shown to be capable of finding anything"
        )
        assert rates == sorted(rates), (
            f"{entry['estimator']}: the detection rate falls as the planted effect grows, which "
            f"is not a sensitivity curve"
        )
        assert entry["minimum_detectable_effect"] in effects


def test_the_effective_observation_count_is_stated_and_is_far_below_the_row_count() -> None:
    """Two thousand rows at a twenty day horizon are not two thousand observations."""
    for entry in summary()["verdicts"]:
        assert entry["effective_observations"] * 5 < entry["observations"], (
            f"{entry['estimator']} reports {entry['effective_observations']} effective "
            f"observations from {entry['observations']} rows, which is not what a "
            f"{summary()['horizon_trading_days']} day horizon implies"
        )


def test_the_empirical_p_is_never_zero_and_matches_the_rank() -> None:
    """A finite ensemble cannot support a p of zero, and the two numbers must agree."""
    for entry in summary()["verdicts"]:
        expected = (entry["rank_in_the_null"] + 1) / (entry["ensemble_size"] + 1)
        assert abs(entry["empirical_p"] - expected) < 1e-6
        assert entry["empirical_p"] > 0


def test_both_estimator_families_were_run_and_a_disagreement_would_be_recorded() -> None:
    """Running one family and reporting it as the answer is the failure this guards."""
    numbers = summary()
    families = {entry["estimator"] for entry in numbers["verdicts"]}
    assert len(families) == 2, f"only {families} was run, so the verdict is one model's opinion"
    assert "estimators_disagree" in numbers, (
        "the summary does not record whether the two families agreed, so a disagreement would "
        "have been silent"
    )


def test_the_transcript_refuses_to_claim_more_than_a_bounded_procedure_can() -> None:
    """The sentence that has to be there, and the ones that must not."""
    text = transcript()
    assert "bound what THIS procedure could have detected" in text
    assert "correct for no multiple comparison" in text
    for forbidden in ("proves", "guarantees", "eliminates", "no leakage", "signal"):
        assert forbidden not in text.lower(), (
            f"the transcript uses {forbidden!r}, which claims more than a control on one frame "
            f"can support"
        )


def test_the_provenance_hash_is_recorded_and_is_a_sha256() -> None:
    """The seam a downstream repository checks."""
    digest = summary()["provenance_sha256"]
    assert len(digest) == 64 and set(digest) <= set("0123456789abcdef")
    assert digest in transcript(), "the hash is in the summary and not in what a reader sees"
