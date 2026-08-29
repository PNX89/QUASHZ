"""The admission verdict: what the frame is, what it refused, and what could have been found.

WHAT A VERDICT IS HERE. Four numbers and a hash:

    the rejection rate, with its reasons
    the candidate's rank inside an empirical null built by permutation
    the minimum detectable effect, from a swept positive control
    a provenance hash over the admitted frame and the rule that admitted it

WHAT IT IS NOT. It is not a claim that the data is clean, that there is no leakage, or that a
relationship exists or does not. The controls bound what THIS procedure could have detected at a
stated effect size on THIS frame. They prove no absence of anything.

TWO ESTIMATOR FAMILIES, AND A DISAGREEMENT IS REPORTED RATHER THAN RESOLVED. A linear model and
a gradient boosting model are run over the same splits. If they reach different verdicts, that
is a property of the estimator and the verdict says so, because the alternative is picking the
one that agrees with what was wanted.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .controls import DetectionCurve, NullResult, detection_curve, permutation_null
from .ledger import ADMISSION_SQL
from .splitter import effective_observations, purged_splits

#: The trading day gap the splitter purges, which is the frame's own horizon.
HORIZON = 20

#: A further band each side of every scoring block. Twice the horizon, because a feature can
#: carry information about a neighbouring block that the target's own window does not cover.
EMBARGO = 40

#: The block length for the permutation null, in trading days. Set to the horizon, so a permuted
#: target keeps blocks at least as long as the dependence being controlled for.
BLOCK_LENGTH = HORIZON

ESTIMATORS = ("logistic regression", "histogram gradient boosting")


def _model(name: str) -> Any:
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    if name == "logistic regression":
        return make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
    if name == "histogram gradient boosting":
        return HistGradientBoostingClassifier(max_iter=100, random_state=0)
    raise ValueError(f"unknown estimator {name!r}")


def cross_validated_auc(name: str) -> Any:
    """A scorer over the purged and embargoed splits, as a callable of (features, target).

    Returned as a closure rather than a method so that `controls.permutation_null` can stay
    ignorant of scikit-learn, the splits and this repository's frame.
    """
    from sklearn.metrics import roc_auc_score

    def score(features: np.ndarray, target: np.ndarray) -> float:
        aucs: list[float] = []
        for split in purged_splits(len(target), horizon=HORIZON, embargo=EMBARGO, folds=5):
            fit = np.asarray(split.fit)
            held = np.asarray(split.score)
            if len(np.unique(target[fit])) < 2 or len(np.unique(target[held])) < 2:
                # A fold whose fitting or scoring block is one class carries no information
                # about ranking, and scoring it would report 0.5 as though it were a result.
                continue
            model = _model(name)
            model.fit(features[fit], target[fit])
            probabilities = model.predict_proba(features[held])[:, 1]
            aucs.append(float(roc_auc_score(target[held], probabilities)))
        return float(np.mean(aucs)) if aucs else 0.5

    return score


@dataclass(frozen=True)
class Verdict:
    """One estimator's answer, with everything needed to argue with it."""

    estimator: str
    observations: int
    effective_observations: int
    null: NullResult
    curve: DetectionCurve
    detected: bool = field(init=False)

    def __post_init__(self) -> None:
        # An effect is called detected only when the candidate beats the null at the same
        # threshold the sweep was measured at. One rule, applied to both.
        object.__setattr__(self, "detected", self.null.empirical_p <= 1 - self.curve.threshold)

    def as_dict(self) -> dict[str, Any]:
        return {
            "estimator": self.estimator,
            "observations": self.observations,
            "effective_observations": self.effective_observations,
            "observed_auc": round(self.null.observed, 6),
            "ensemble_size": self.null.ensemble_size,
            "block_length": self.null.block_length,
            "rank_in_the_null": self.null.rank,
            "empirical_p": round(self.null.empirical_p, 6),
            "null_median": round(float(np.median(self.null.permuted)), 6),
            "null_max": round(float(np.max(self.null.permuted)), 6),
            "detection_effects": list(self.curve.effects),
            "detection_rates": list(self.curve.detected),
            "minimum_detectable_effect": self.curve.minimum_detectable_effect,
            "detected": self.detected,
        }


def provenance(features: np.ndarray, target: np.ndarray, *, horizon: int) -> str:
    """A hash over the admitted frame AND the rule that admitted it.

    THE RULE IS IN THE HASH ON PURPOSE. Two frames with identical numbers admitted under
    different predicates are not the same dataset, and a hash of the values alone would call
    them equal. This is the seam a downstream repository checks: a challenger promoted against a
    frame whose provenance hash is unknown is a challenger nobody can reproduce.
    """
    digest = hashlib.sha256()
    digest.update(np.ascontiguousarray(features, dtype=np.float64).tobytes())
    digest.update(np.ascontiguousarray(target, dtype=np.int64).tobytes())
    digest.update(json.dumps({"horizon": horizon, "predicate": ADMISSION_SQL}).encode("utf-8"))
    return digest.hexdigest()


def run(
    features: np.ndarray,
    target: np.ndarray,
    *,
    ensemble: int,
    effects: Sequence[float],
    repeats: int,
    threshold: float = 0.95,
    seed: int = 20260829,
) -> list[Verdict]:
    """Both estimator families over the same frame, splits, null and sweep."""
    verdicts: list[Verdict] = []
    for name in ESTIMATORS:
        scorer = cross_validated_auc(name)
        null = permutation_null(
            scorer, features, target, block_length=BLOCK_LENGTH, ensemble=ensemble, seed=seed
        )
        # The sweep is measured against the null's own upper tail, so the positive and negative
        # controls share one yardstick instead of each carrying a different arbitrary line.
        reference = float(np.quantile(null.permuted, threshold))
        curve = detection_curve(
            scorer,
            features,
            effects=effects,
            repeats=repeats,
            threshold=threshold,
            seed=seed + 1,
            reference=reference,
        )
        verdicts.append(
            Verdict(
                estimator=name,
                observations=len(target),
                effective_observations=effective_observations(len(target), horizon=HORIZON),
                null=null,
                curve=curve,
            )
        )
    return verdicts
