"""Issue the admission verdict, and record everything needed to argue with it.

    uv run --group verdict python scripts/measure_verdict.py

WHAT IS MEASURED, in the order the verdict states it:

    1. the rejection rate, WITH its reasons, because a bare rate hides which rule fired
    2. the candidate's rank inside an empirical null of circular block permutations
    3. the minimum detectable effect, from a swept positive control on the same yardstick
    4. a provenance hash over the admitted frame and the predicate that admitted it

ONE THREAD, AND IT IS NOT A GUESS. At this problem's size, scikit-learn's own thread pool costs
more to coordinate than the fitting it coordinates, for an identical AUC to four decimal places
pinned or not. Neither absolute time is reproducible enough to publish: it is machine dependent
and this repository has nowhere to record it the way every other measured number here is
recorded, under `docs/evidence/`. Lowering the iteration count would also have been fast and
would have changed the answer, which is the difference between a cost saving and a thumb on the
scale.
"""

from __future__ import annotations

import os

# Set BEFORE numpy and scikit-learn are imported, because the thread pools are built at import
# time and a later change is ignored.
for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(variable, "1")

import json  # noqa: E402
import pathlib  # noqa: E402
import sys  # noqa: E402

import numpy as np  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quashz import frame, ledger, verdict  # noqa: E402

OUT = ROOT / "docs" / "evidence" / "verdict"

#: 200 permutations, which fixes the finest p-value this can report at 1 in 201. Printed before
#: the sweep rather than after it, so a reader knows the resolution before seeing the number.
ENSEMBLE = 200

#: The planted effect sizes, in standard deviations of the leading feature. Swept rather than
#: tested at one point, because "it can detect an effect" is not a claim until the effect is
#: named, and the answer wanted is the SMALLEST one it catches.
EFFECTS = (0.05, 0.1, 0.2, 0.4, 0.8, 1.6)
REPEATS = 20
THRESHOLD = 0.95


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    rows, refusals = frame.build()
    connection = ledger.connect()
    held = ledger.write(connection, refusals)
    admitted = ledger.admit(connection, rows)
    if not admitted:
        print("the predicate admitted nothing, so there is no frame to judge", file=sys.stderr)
        return 1

    features = np.array(
        [[level, slope, fx, gdp, age] for _, level, slope, fx, gdp, age, _ in admitted]
    )
    target = np.array([outcome for *_, outcome in admitted])
    digest = verdict.provenance(features, target, horizon=verdict.HORIZON)

    print(f"admitted {len(admitted)} rows, refused {held}")
    print(f"ensemble size {ENSEMBLE}, block length {verdict.BLOCK_LENGTH} trading days")
    verdicts = verdict.run(
        features,
        target,
        ensemble=ENSEMBLE,
        effects=EFFECTS,
        repeats=REPEATS,
        threshold=THRESHOLD,
    )

    summary = {
        "admitted": len(admitted),
        "refused": held,
        "rejection_rate": round(ledger.rate(connection, len(admitted)), 6),
        "refusals_by_reason": [
            {"reason": reason, "rows": count} for reason, count in ledger.by_reason(connection)
        ],
        "features": ["level", "slope", "fx", "gdp", "gdp_age_days"],
        "horizon_trading_days": verdict.HORIZON,
        "embargo_trading_days": verdict.EMBARGO,
        "ensemble": ENSEMBLE,
        "repeats_per_effect": REPEATS,
        "threshold": THRESHOLD,
        "provenance_sha256": digest,
        "verdicts": [entry.as_dict() for entry in verdicts],
    }

    if len({entry.detected for entry in verdicts}) > 1:
        summary["estimators_disagree"] = True
        print(
            "THE TWO ESTIMATOR FAMILIES REACH DIFFERENT VERDICTS. That is reported rather than "
            "resolved: it is a property of the estimator, and picking the one that agrees with "
            "what was wanted is the whole failure this repository is about.",
            file=sys.stderr,
        )
    else:
        summary["estimators_disagree"] = False

    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    with (OUT / "the-verdict.txt").open("w", encoding="utf-8") as handle:
        print("$ uv run --group verdict python scripts/measure_verdict.py", file=handle)
        print(file=handle)
        print(f"ADMITTED   {len(admitted)} rows", file=handle)
        print(
            f"REFUSED    {held} rows, {ledger.rate(connection, len(admitted)):.1%} of everything "
            f"considered",
            file=handle,
        )
        for reason, count in ledger.by_reason(connection):
            print(f"             {count:>5}  {reason}", file=handle)
        print(file=handle)
        print(
            f"The null is {ENSEMBLE} circular block permutations at a block length of "
            f"{verdict.BLOCK_LENGTH} trading days,",
            file=handle,
        )
        print(
            "so the finest p-value it can report is 1 in "
            f"{ENSEMBLE + 1}. The sweep plants an effect at "
            f"{', '.join(str(effect) for effect in EFFECTS)} standard deviations,",
            file=handle,
        )
        print(f"{REPEATS} times each, and the two share one yardstick.", file=handle)
        print(file=handle)
        for entry in verdicts:
            mde = entry.curve.minimum_detectable_effect
            print(f"--- {entry.estimator} ---", file=handle)
            print(
                f"  observed AUC {entry.null.observed:.4f}, rank {entry.null.rank} of "
                f"{entry.null.ensemble_size}, empirical p {entry.null.empirical_p:.4f}",
                file=handle,
            )
            print(
                f"  the null runs to {np.max(entry.null.permuted):.4f} at its maximum and sits "
                f"at {np.median(entry.null.permuted):.4f} in the middle",
                file=handle,
            )
            print(
                "  smallest effect found at the declared rate: "
                + (f"{mde} standard deviations" if mde is not None else "none in this sweep"),
                file=handle,
            )
            print(
                "  detection rates: "
                + ", ".join(
                    f"{effect}={rate:.2f}"
                    for effect, rate in zip(entry.curve.effects, entry.curve.detected, strict=True)
                ),
                file=handle,
            )
            print(
                f"  {entry.observations} rows, which at a {verdict.HORIZON} day horizon is "
                f"{entry.effective_observations} effectively independent observations",
                file=handle,
            )
            print(file=handle)
        print(f"provenance {digest}", file=handle)
        print(file=handle)
        print(
            "The controls bound what THIS procedure could have detected on THIS frame at the "
            "effect sizes swept.",
            file=handle,
        )
        print(
            "They are not evidence that there is no relationship, and they correct for no "
            "multiple comparison:",
            file=handle,
        )
        print(
            "an empirical null says where one score sits under one hypothesis, and says nothing "
            "about how many were tried.",
            file=handle,
        )

    print((OUT / "the-verdict.txt").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
