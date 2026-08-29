"""The permutation the controls rest on, searched rather than eyeballed.

THE DEFECT THIS FILE EXISTS BECAUSE OF. The first circular block permutation cut from fixed
starts and wrapped each block with a modulo. At 10 observations and a block length of 4 it
returned index 0 and index 1 twice and dropped 2 and 3 entirely, so the "permuted" target was a
sample that never existed, and every null score computed from it was of the wrong thing. It ran
perfectly. It was found by printing one, and it is now held by a property over every shape.
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from quashz.controls import DetectionCurve, NullResult, circular_block_permutation

settings.register_profile("quashz", deadline=None, suppress_health_check=[HealthCheck.too_slow])
settings.load_profile("quashz")


@given(
    st.integers(min_value=1, max_value=300),
    st.integers(min_value=1, max_value=80),
    st.integers(min_value=0, max_value=2**32 - 1),
)
def test_the_permutation_is_always_a_bijection(n_obs: int, block_length: int, seed: int) -> None:
    """Every index exactly once, at every shape, including the ones that do not divide."""
    order = circular_block_permutation(
        n_obs, block_length=block_length, rng=np.random.default_rng(seed)
    )
    assert sorted(order.tolist()) == list(range(n_obs)), (
        f"n={n_obs} L={block_length} produced {len(set(order.tolist()))} distinct indices"
    )


@given(
    st.integers(min_value=2, max_value=300),
    st.integers(min_value=1, max_value=60),
    st.integers(min_value=0, max_value=2**32 - 1),
)
def test_the_permutation_keeps_most_neighbours_adjacent(
    n_obs: int, block_length: int, seed: int
) -> None:
    """The property that makes it a BLOCK permutation rather than a shuffle.

    A row by row shuffle destroys the target's own autocorrelation as well as its pairing with
    the features, which builds a null for an easier problem. What is asserted is the mechanism
    rather than a statistic: the number of positions whose original neighbour is still their
    neighbour has to be at least what whole blocks guarantee.
    """
    order = circular_block_permutation(
        n_obs, block_length=block_length, rng=np.random.default_rng(seed)
    )
    kept = sum(1 for a, b in pairwise(order) if b == a + 1)
    blocks = -(-n_obs // block_length)
    # THE BOUND IS n - B - 1 AND MY FIRST ONE WAS n - B, which the search falsified at n=2, L=2
    # in a few dozen examples. B blocks preserve n - B internal adjacencies, and the rotation
    # costs one more: the block containing the wrap point is contiguous in the ROTATED index and
    # is two pieces of the original. Being wrong about the bound and not about the code is the
    # ordinary result of writing a property test, and the counterexample is why the bound is
    # right now rather than approximately right.
    assert kept >= n_obs - blocks - 1, (
        f"only {kept} of {n_obs - 1} adjacencies survived, which is fewer than {blocks} blocks "
        f"of length {block_length} plus one rotation can account for"
    )


@pytest.mark.parametrize(("n_obs", "block_length"), [(10, 4), (10, 3), (7, 9), (1, 1), (100, 20)])
def test_the_shapes_that_broke_it_stay_covered(n_obs: int, block_length: int) -> None:
    """Promoted from counterexamples, so a shrinking search cannot stop covering them."""
    order = circular_block_permutation(
        n_obs, block_length=block_length, rng=np.random.default_rng(11)
    )
    assert sorted(order.tolist()) == list(range(n_obs))


@pytest.mark.parametrize(("n_obs", "block_length"), [(0, 4), (-1, 4), (10, 0), (10, -3)])
def test_impossible_shapes_raise(n_obs: int, block_length: int) -> None:
    with pytest.raises(ValueError):
        circular_block_permutation(n_obs, block_length=block_length, rng=np.random.default_rng(0))


def test_the_empirical_p_value_can_never_be_zero() -> None:
    """A finite ensemble cannot support a p of zero, so the convention is (rank + 1) / (n + 1)."""
    beaten_by_none = NullResult(observed=10.0, permuted=(1.0, 2.0, 3.0), block_length=5)
    assert beaten_by_none.rank == 0
    assert beaten_by_none.empirical_p == pytest.approx(0.25)
    assert beaten_by_none.empirical_p > 0


def test_the_rank_counts_ties_against_the_candidate() -> None:
    """A permutation that equals the observed score is evidence against it, not for it."""
    tied = NullResult(observed=2.0, permuted=(1.0, 2.0, 3.0), block_length=5)
    assert tied.rank == 2


def test_a_sweep_that_never_reaches_the_threshold_reports_no_detectable_effect() -> None:
    """Reporting the largest effect tried instead would be the reassuring answer and a false one."""
    curve = DetectionCurve(effects=(0.1, 0.2), detected=(0.1, 0.2), threshold=0.8)
    assert curve.minimum_detectable_effect is None

    found = DetectionCurve(effects=(0.1, 0.2, 0.4), detected=(0.1, 0.5, 0.9), threshold=0.8)
    assert found.minimum_detectable_effect == 0.4
