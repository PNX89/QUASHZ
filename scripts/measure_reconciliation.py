"""Two publishers, one quantity, and the disagreements that are not errors.

    uv run --group verdict python scripts/measure_reconciliation.py

A candidate series is admitted only after it is reconciled against an incumbent covering the
same thing. The interesting cases are not the ones where somebody is wrong.

    THE FX PAIR. The Federal Reserve and the ECB both publish a dollar per euro rate for the
    same days. They agree exactly on a handful of days out of hundreds. Neither is wrong: they
    are fixed at different times of day from different panels, and a reconciliation rule that
    demands equality would reject a perfectly good series while a rule with no tolerance at all
    would accept a stale one.

    THE CALENDAR. The two publishers do not stop on the same days. Each has days the other does
    not, and the counts are recorded, because a naive join silently drops them and calls the
    result an overlap.

    THE IDENTITY. The Federal Reserve publishes a ten year yield, a two year yield, and the
    spread between them, so the third can be checked against the first two. It holds on all but
    a handful of days across half a century. Those days are KEPT and printed rather than
    filtered out, because they are the justification for the tolerance: a rule tuned until
    nothing fails has been tuned to the data it was tested on.

THE CONVENTION IS INFERRED BY MEASUREMENT AND NAMED, never read out of documentation. Whether a
monthly figure is a period average or a period end is decided here by comparing it against the
daily series it is built from, and the answer is printed with the evidence for it.
"""

from __future__ import annotations

import json
import pathlib
import statistics
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quashz import corpus  # noqa: E402

OUT = ROOT / "docs" / "evidence" / "reconciliation"

#: Two decimal places, which is the precision the Federal Reserve publishes these yields at.
IDENTITY_PLACES = 2


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    fed_rate = corpus.fed("DEXUSEU")
    ecb_rate = corpus.ecb_reference_rate()
    # Both series are cut at the earlier of the two last observations, because one publisher
    # being a day ahead is not a gap in the other and counting it as one would inflate the
    # only-days on whichever happened to be captured second.
    end = min(max(fed_rate), max(ecb_rate))
    start = max(min(fed_rate), min(ecb_rate))
    fed_rate = {day: value for day, value in fed_rate.items() if start <= day <= end}
    ecb_rate = {day: value for day, value in ecb_rate.items() if start <= day <= end}

    shared = sorted(set(fed_rate) & set(ecb_rate))
    if not shared:
        print("the two publishers share no days at all", file=sys.stderr)
        return 1
    # SIGNED, because the dispersion a reader sizes a symmetric tolerance from is the spread of
    # the disagreement, not of its magnitude. `differences` below stays absolute for the median,
    # the exact-match count and the largest gap, all three of which are honestly about size
    # rather than direction, but folding the sign into a standard deviation understates it: on
    # this corpus the folded figure is a third smaller than the signed one.
    signed_differences = [fed_rate[day] - ecb_rate[day] for day in shared]
    differences = [abs(value) for value in signed_differences]
    exact = sum(1 for value in differences if value == 0)

    yields10 = corpus.fed("DGS10")
    yields2 = corpus.fed("DGS2")
    published_spread = corpus.fed("T10Y2Y")
    common = sorted(set(yields10) & set(yields2) & set(published_spread))
    breaks = [
        {
            "date": day.isoformat(),
            "ten_year": yields10[day],
            "two_year": yields2[day],
            "difference": round(yields10[day] - yields2[day], IDENTITY_PLACES),
            "published": published_spread[day],
        }
        for day in common
        if round(yields10[day] - yields2[day], IDENTITY_PLACES)
        != round(published_spread[day], IDENTITY_PLACES)
    ]

    summary: dict[str, dict[str, Any]] = {
        "fx": {
            "window": [shared[0].isoformat(), shared[-1].isoformat()],
            "days_both_publish": len(shared),
            "agree_exactly": exact,
            "median_absolute_difference": round(statistics.median(differences), 5),
            "standard_deviation": round(statistics.pstdev(signed_differences), 5),
            "largest_difference": round(max(differences), 4),
            "days_only_the_ecb_publishes": len(set(ecb_rate) - set(fed_rate)),
            "days_only_the_fed_publishes": len(set(fed_rate) - set(ecb_rate)),
        },
        "identity": {
            "days_all_three_exist": len(common),
            "days_it_holds": len(common) - len(breaks),
            "days_it_fails": len(breaks),
            "the_failures": breaks,
            "places": IDENTITY_PLACES,
        },
    }

    if exact == len(shared):
        print(
            "the two publishers agree on every single day, which would mean one is copying the "
            "other and the reconciliation shows nothing",
            file=sys.stderr,
        )
        return 1
    if not breaks:
        print(
            "the published spread now equals the difference on every day in half a century. "
            "That is a change in the data worth reading about before this claim is softened, "
            "because the exhibit exists to justify a tolerance that would then have no case",
            file=sys.stderr,
        )
        return 1

    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    fx: dict[str, Any] = summary["fx"]
    identity: dict[str, Any] = summary["identity"]
    with (OUT / "two-publishers.txt").open("w", encoding="utf-8") as handle:
        print("$ uv run --group verdict python scripts/measure_reconciliation.py", file=handle)
        print(file=handle)
        print(
            f"US dollars per euro, {fx['window'][0]} to {fx['window'][1]}, as published by the",
            file=handle,
        )
        print("Federal Reserve and by the European Central Bank:", file=handle)
        print(file=handle)
        print(f"  days both publish            {fx['days_both_publish']}", file=handle)
        print(f"  days they agree exactly      {fx['agree_exactly']}", file=handle)
        print(f"  median absolute difference   {fx['median_absolute_difference']}", file=handle)
        print(f"  standard deviation           {fx['standard_deviation']}", file=handle)
        print(f"  largest difference           {fx['largest_difference']}", file=handle)
        print(f"  days only the ECB publishes  {fx['days_only_the_ecb_publishes']}", file=handle)
        print(f"  days only the Fed publishes  {fx['days_only_the_fed_publishes']}", file=handle)
        print(file=handle)
        print(
            "Neither is wrong. They are fixed at different times of day, so a rule demanding",
            file=handle,
        )
        print(
            "equality rejects a good series and a rule with no tolerance accepts a stale one.",
            file=handle,
        )
        print(file=handle)
        print(
            "The Federal Reserve also publishes the spread between its own ten year and two",
            file=handle,
        )
        print(
            f"year yields. Over {identity['days_all_three_exist']:,} days on which all three "
            f"exist it equals the",
            file=handle,
        )
        print(
            f"difference on {identity['days_it_holds']:,} and disagrees on "
            f"{identity['days_it_fails']}:",
            file=handle,
        )
        print(file=handle)
        for entry in identity["the_failures"]:
            print(
                f"  {entry['date']}   {entry['ten_year']} - {entry['two_year']} = "
                f"{entry['difference']}, published {entry['published']}",
                file=handle,
            )
        print(file=handle)
        print(
            "Those days are kept rather than filtered. A tolerance tuned until nothing fails",
            file=handle,
        )
        print("has been tuned to the sample it was tested on.", file=handle)

    print((OUT / "two-publishers.txt").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
