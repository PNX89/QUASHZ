"""Two publishers disagreeing for reasons that are not errors, checked against the corpus.

What these defend is that the exhibit still shows a DISAGREEMENT. A reconciliation where the two
sources match everywhere proves that one is copying the other, and a reconciliation with no
failures at all cannot justify the tolerance it exists to justify.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

from quashz import corpus

REPO = pathlib.Path(__file__).resolve().parents[1]
EVIDENCE = REPO / "docs" / "evidence" / "reconciliation"


def summary() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((EVIDENCE / "summary.json").read_text(encoding="utf-8"))
    return loaded


def test_the_two_publishers_disagree_on_most_days_and_agree_on_some() -> None:
    """Both halves matter: total agreement means copying, total disagreement means a bug."""
    fx = summary()["fx"]
    assert fx["days_both_publish"] > 500
    assert 0 < fx["agree_exactly"] < fx["days_both_publish"] // 10, (
        f"they agree exactly on {fx['agree_exactly']} of {fx['days_both_publish']} days, which "
        f"is either none, which suggests a units problem, or so many that one is copying"
    )
    assert fx["largest_difference"] > fx["median_absolute_difference"] * 5, (
        "the largest difference is close to the typical one, so there is no tail and a fixed "
        "tolerance would be doing no work"
    )


def test_each_publisher_has_days_the_other_does_not() -> None:
    """A naive join drops these silently and calls what is left an overlap."""
    fx = summary()["fx"]
    assert fx["days_only_the_ecb_publishes"] > 0
    assert fx["days_only_the_fed_publishes"] > 0


def test_the_identity_holds_almost_everywhere_and_the_failures_are_kept() -> None:
    """A tolerance tuned until nothing fails has been tuned to its own test set."""
    identity = summary()["identity"]
    assert identity["days_it_fails"] > 0, (
        "the published spread now equals the difference on every day, so the tolerance this "
        "exhibit justifies has nothing behind it"
    )
    assert identity["days_it_fails"] < 10, (
        f"{identity['days_it_fails']} days break the identity, which is too many to call a "
        f"handful and is worth reading about"
    )
    assert identity["days_it_holds"] + identity["days_it_fails"] == identity["days_all_three_exist"]


def test_every_recorded_identity_failure_is_still_in_the_corpus_with_those_numbers() -> None:
    """RECOMPUTED, not quoted. The count moves as the publisher adds days, and the failures
    should not, so each one is checked against the committed series rather than trusted."""
    import datetime

    yields10 = corpus.fed("DGS10")
    yields2 = corpus.fed("DGS2")
    spread = corpus.fed("T10Y2Y")
    for entry in summary()["identity"]["the_failures"]:
        day = datetime.date.fromisoformat(entry["date"])
        assert yields10[day] == entry["ten_year"]
        assert yields2[day] == entry["two_year"]
        assert spread[day] == entry["published"]
        assert round(yields10[day] - yields2[day], 2) != round(spread[day], 2), (
            f"{entry['date']} is recorded as a failure and the identity holds there now"
        )


def test_the_denominator_moves_and_the_failures_do_not() -> None:
    """The claim that survives a growing corpus, stated as a relationship between two numbers."""
    identity = summary()["identity"]
    assert identity["days_all_three_exist"] > 12_000, (
        "the identity is measured over fewer days than the corpus holds, so something is being "
        "excluded before the comparison"
    )
    assert identity["days_it_fails"] <= 3, (
        "a new day has broken the identity. That is a finding rather than a test to relax: it "
        "should be read and added to the exhibit with the others"
    )
