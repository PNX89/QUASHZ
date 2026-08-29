"""The two controls that decide whether a null result means anything.

A pipeline that reports no relationship has said nothing until two more questions are answered:
could it have found one, and how small a one. Both are measured here, and neither is a claim
about leakage. **The controls bound what this procedure could have detected at a stated effect
size. They do not prove the absence of information, and no sentence anywhere in this repository
says they do.**

THE NEGATIVE CONTROL IS AN ENSEMBLE, NOT A DRAW. A single permuted fit gives one number, and one
number from a null distribution tells you nothing about where the real score sits in it. So the
target is permuted many times and the candidate's score is reported as its RANK inside that
empirical null, with the whole distribution kept.

THE PERMUTATION IS CIRCULAR AND BLOCKED, AND THAT IS NOT A DETAIL. Shuffling a target with a
twenty day horizon row by row destroys its serial correlation as well as its relationship to the
features, so the null it builds is a null for a problem nobody has: an easier one. Permuting
CONTIGUOUS BLOCKS, wrapped circularly, keeps the target's own autocorrelation and destroys only
the pairing.

WHAT THIS IS NOT. QUACKZ owns the stationary bootstrap, the Sharpe ratio and the deflated Sharpe,
and none of them is reimplemented here. A circular block permutation is a different object from
a stationary bootstrap: fixed block lengths rather than geometric, without replacement rather
than with, and built to destroy a pairing rather than to resample a distribution. Using one for
the other would run and would be wrong.

AND AN EMPIRICAL NULL IS NOT A MULTIPLE-COMPARISONS CORRECTION. Calibrating a score against a
permutation distribution says where this score sits under the hypothesis of no relationship. It
says nothing about how many hypotheses were tried, and it corrects for none of them.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class NullResult:
    """Where a score sits inside the permutation null, with the null kept rather than summarised."""

    observed: float
    permuted: tuple[float, ...]
    block_length: int

    @property
    def ensemble_size(self) -> int:
        return len(self.permuted)

    @property
    def rank(self) -> int:
        """How many permutations reached the observed score. Zero means it beat all of them."""
        return int(np.sum(np.asarray(self.permuted) >= self.observed))

    @property
    def empirical_p(self) -> float:
        """(rank + 1) / (n + 1), which cannot return zero.

        A p-value of exactly zero from a finite ensemble is a claim no finite ensemble can
        support. The plus-one convention says "below one in n+1" and is the standard one.
        """
        return (self.rank + 1) / (self.ensemble_size + 1)


def circular_block_permutation(
    n_obs: int, *, block_length: int, rng: np.random.Generator
) -> np.ndarray:
    """An index permutation built from contiguous blocks of a randomly rotated sample.

    THE ROTATION IS WHERE THE CIRCULARITY LIVES, and the first version of this put it in the
    blocks instead: it cut from fixed starts and wrapped each block with a modulo, which is not
    a permutation at all when the block length does not divide the sample. At n=10 and L=4 it
    returned index 0 and index 1 twice and dropped 2 and 3 entirely, so a "permuted" target
    silently contained duplicated rows and was missing others. It ran, and every score it
    produced was of a sample that did not exist.

    What is done instead: rotate the whole index by a random offset, cut the rotated index into
    consecutive blocks with a short one at the end, shuffle the blocks. Every index appears
    exactly once by construction, the rotation makes every cut point reachable across draws, and
    the blocks stay contiguous in the original series, which is the property that preserves the
    target's own autocorrelation.
    """
    if block_length <= 0:
        raise ValueError("a block length is a length")
    if n_obs <= 0:
        raise ValueError("n_obs must be positive")
    rotated = np.roll(np.arange(n_obs), int(rng.integers(0, n_obs)))
    blocks = [rotated[start : start + block_length] for start in range(0, n_obs, block_length)]
    order = rng.permutation(len(blocks))
    return np.concatenate([blocks[index] for index in order])


def permutation_null(
    fit_and_score: object,
    features: np.ndarray,
    target: np.ndarray,
    *,
    block_length: int,
    ensemble: int,
    seed: int,
) -> NullResult:
    """Score the candidate, then score `ensemble` circular block permutations of the target.

    `fit_and_score` is any callable taking (features, target) and returning one number. The
    caller owns the estimator and the splitting, so this file has no opinion about either.
    """
    if ensemble < 2:
        raise ValueError("an ensemble of one is a draw, and a draw locates nothing")
    scorer = fit_and_score
    assert callable(scorer)

    rng = np.random.default_rng(seed)
    observed = float(scorer(features, target))
    permuted: list[float] = []
    for _ in range(ensemble):
        order = circular_block_permutation(len(target), block_length=block_length, rng=rng)
        permuted.append(float(scorer(features, target[order])))
    return NullResult(observed=observed, permuted=tuple(permuted), block_length=block_length)


@dataclass(frozen=True)
class DetectionCurve:
    """What the procedure could have found, swept rather than asserted at one point."""

    effects: tuple[float, ...]
    detected: tuple[float, ...]
    threshold: float

    @property
    def minimum_detectable_effect(self) -> float | None:
        """The smallest planted effect the procedure caught at or above the declared rate.

        Returns None when the sweep never reached the threshold, which is a real answer and is
        reported as one rather than as the largest effect tried.
        """
        for effect, rate in zip(self.effects, self.detected, strict=True):
            if rate >= self.threshold:
                return effect
        return None


def detection_curve(
    fit_and_score: object,
    features: np.ndarray,
    *,
    effects: Sequence[float],
    repeats: int,
    threshold: float,
    seed: int,
    reference: float,
) -> DetectionCurve:
    """Plant an effect of known size, repeatedly, and record how often it is found.

    The planted target is built from the features themselves plus noise, so the only thing
    varying across the sweep is the strength of the relationship. `reference` is the score the
    permutation null puts at the detection boundary, so this and the negative control are
    measured against the same yardstick rather than two different ones.
    """
    scorer = fit_and_score
    assert callable(scorer)
    rng = np.random.default_rng(seed)
    signal = features[:, 0]
    signal = (signal - signal.mean()) / (signal.std() or 1.0)

    rates: list[float] = []
    for effect in effects:
        hits = 0
        for _ in range(repeats):
            noise = rng.standard_normal(len(signal))
            planted = (effect * signal + noise > 0).astype(int)
            if float(scorer(features, planted)) >= reference:
                hits += 1
        rates.append(hits / repeats)
    return DetectionCurve(effects=tuple(effects), detected=tuple(rates), threshold=threshold)
