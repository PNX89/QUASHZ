"""The splitter's guarantees, stated as properties and searched for rather than authored.

An example test asks whether the case the author thought of works. A property test asks the
library to find a case that does not, and the counterexample it returns is one nobody wrote
down. Every counterexample found here has been promoted to an explicit example, so a shrinking
search that gets unlucky cannot quietly stop covering it.
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from quashz.splitter import Split, effective_observations, purged_splits

# One profile, no deadline. A per-example deadline turns a slow machine into a failing build,
# which is a flake wearing the clothes of a finding.
settings.register_profile("quashz", deadline=None, suppress_health_check=[HealthCheck.too_slow])
settings.load_profile("quashz")


@st.composite
def panels(draw: st.DrawFn) -> tuple[int, int, int, int]:
    """Valid parameters, built rather than filtered.

    Generating freely and discarding with `assume` is how a property test ends up exercising
    the corner of the space that happens to survive. The constraints are in the strategy.
    """
    folds = draw(st.integers(min_value=2, max_value=6))
    n_obs = draw(st.integers(min_value=folds, max_value=400))
    horizon = draw(st.integers(min_value=0, max_value=60))
    embargo = draw(st.integers(min_value=0, max_value=30))
    return n_obs, horizon, embargo, folds


@given(panels())
def test_no_fitting_index_lies_within_the_horizon_of_a_scoring_index(
    panel: tuple[int, int, int, int],
) -> None:
    """The purge, which is the guarantee the whole splitter exists for."""
    n_obs, horizon, embargo, folds = panel
    for split in purged_splits(n_obs, horizon=horizon, embargo=embargo, folds=folds):
        for scored in split.score:
            for fitted in split.fit:
                assert abs(fitted - scored) > horizon, (
                    f"a fitting index at {fitted} is {abs(fitted - scored)} from a scoring index "
                    f"at {scored}, inside a horizon of {horizon}"
                )


@pytest.mark.parametrize(
    ("n_obs", "horizon", "folds"),
    [(100, 7, 4), (60, 0, 3), (37, 12, 5), (400, 60, 2), (9, 3, 3)],
)
def test_the_purge_alone_clears_the_window_around_every_scoring_block(
    n_obs: int, horizon: int, folds: int
) -> None:
    """THE PURGE ON ITS OWN, with the embargo set to nothing so nothing else can be doing it.

    This is the direct test the purge did not have. The property test below asserts a band is
    clear, and the band it asserts was cleared twice over: the embargo bounds used to be written
    from the scoring block rather than from the end of the purged window, so they covered the
    horizon themselves. Deleting the horizon from the purge loop entirely changed no output and
    left both suites green, which is a guarantee nobody was watching.

    With `embargo=0` the two bands are empty ranges, so the fitting set below is the purge and
    nothing else, and it is asserted exactly rather than as a containment: a purge that is too
    wide throws away fitting rows for no reason, and that is worth a red build too.
    """
    for split in purged_splits(n_obs, horizon=horizon, embargo=0, folds=folds):
        start, stop = split.score[0], split.score[-1] + 1
        expected = tuple(
            index for index in range(n_obs) if not start - horizon <= index < stop + horizon
        )
        assert split.fit == expected, (
            f"with no embargo the fitting set for [{start}, {stop}) at a horizon of {horizon} "
            f"should be everything outside [{start - horizon}, {stop + horizon})"
        )


@given(panels())
def test_the_embargo_is_applied_on_both_sides_of_every_boundary(
    panel: tuple[int, int, int, int],
) -> None:
    """The asymmetric version of this is the common one, and it passes a one-sided test."""
    n_obs, horizon, embargo, folds = panel
    for split in purged_splits(n_obs, horizon=horizon, embargo=embargo, folds=folds):
        start, stop = split.score[0], split.score[-1] + 1
        banned = set(range(start - horizon - embargo, start)) | set(
            range(stop, stop + horizon + embargo)
        )
        assert not banned & set(split.fit), (
            f"the band around [{start}, {stop}) is not clear: {sorted(banned & set(split.fit))[:5]}"
        )


@given(panels())
def test_no_observation_is_in_both_blocks(panel: tuple[int, int, int, int]) -> None:
    n_obs, horizon, embargo, folds = panel
    for split in purged_splits(n_obs, horizon=horizon, embargo=embargo, folds=folds):
        assert not set(split.fit) & set(split.score)


@given(
    st.integers(min_value=10, max_value=400),
    st.integers(min_value=0, max_value=40),
    st.integers(min_value=0, max_value=40),
)
def test_the_effective_count_never_rises_when_the_horizon_does(
    n_obs: int, shorter: int, longer: int
) -> None:
    """Monotonicity, which is the property that catches an off-by-one in the divisor."""
    low, high = sorted((shorter, longer))
    assert effective_observations(n_obs, horizon=high) <= effective_observations(n_obs, horizon=low)


@given(panels())
def test_every_scoring_block_is_contiguous_and_the_blocks_tile_the_sample(
    panel: tuple[int, int, int, int],
) -> None:
    """Otherwise a row can be scored twice, or never."""
    n_obs, horizon, embargo, folds = panel
    splits = purged_splits(n_obs, horizon=horizon, embargo=embargo, folds=folds)
    scored: list[int] = []
    for split in splits:
        block = list(split.score)
        assert block == list(range(block[0], block[-1] + 1)), "a scoring block has a hole in it"
        scored += block
    assert sorted(scored) == list(range(n_obs)), "the scoring blocks do not tile the sample"


def test_a_split_refuses_to_exist_with_an_index_on_both_sides() -> None:
    """The invariant is enforced in the type rather than only in the function that builds it."""
    with pytest.raises(ValueError, match="both"):
        Split(fit=(1, 2, 3), score=(3, 4))


@pytest.mark.parametrize(
    ("n_obs", "horizon", "embargo", "folds", "message"),
    [
        (10, 5, 0, 1, "single fold"),
        (3, 1, 0, 5, "cannot be cut"),
        (10, -1, 0, 5, "negative"),
        (0, 1, 0, 5, "positive"),
    ],
)
def test_impossible_parameters_raise_rather_than_returning_something_degenerate(
    n_obs: int, horizon: int, embargo: int, folds: int, message: str
) -> None:
    """A splitter that silently returns an empty fitting set produces a score from nothing."""
    with pytest.raises(ValueError, match=message):
        purged_splits(n_obs, horizon=horizon, embargo=embargo, folds=folds)
