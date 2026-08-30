"""The scorer's reaction to a target with nothing to rank, checked rather than assumed.

THE DEFECT THIS FILE EXISTS BECAUSE OF. Every fold's fitting or scoring block being single
class is exactly the case the loop's own comment says must not be reported as 0.5, because
scoring a one class block "would report 0.5 as though it were a result". The terminal fallback
on the return line did precisely that when every fold was skipped: `np.mean` of an empty list is
`nan`, silently rescued by `... if aucs else 0.5`. With the frame's real target this path was
never reached, so the inconsistency lived in the code rather than in any published number.
"""

from __future__ import annotations

import numpy as np
import pytest

from quashz.verdict import cross_validated_auc


def test_a_target_with_no_ranking_information_in_any_fold_raises_rather_than_scoring_0_5() -> None:
    """Three positives in three hundred rows, purged over 5 folds: every fold is single class.

    Reproduced directly rather than argued: before this fix `score(features, target)` here
    returned 0.5, the exact number the skip's own comment names as indistinguishable from a
    real result.
    """
    rng = np.random.default_rng(0)
    target = np.zeros(300)
    target[:3] = 1
    features = rng.standard_normal((300, 3))
    score = cross_validated_auc("logistic regression")
    with pytest.raises(ValueError, match="single class"):
        score(features, target)


def test_a_target_with_ranking_information_still_scores_normally() -> None:
    """The fix must not turn an ordinary run into a raise: a balanced target still averages."""
    rng = np.random.default_rng(0)
    target = (rng.standard_normal(300) > 0).astype(float)
    features = rng.standard_normal((300, 3))
    score = cross_validated_auc("logistic regression")
    result = score(features, target)
    assert 0.0 <= result <= 1.0
