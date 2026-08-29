"""A splitter that puts the horizon between the block fitted on and the block scored on.

WHY THE ORDINARY ONE IS WRONG HERE. A row's outcome is measured over the following twenty
trading days, so two rows twenty days apart share nineteen days of the same future. Shuffling
them into different folds puts most of a scoring row's answer into the fitting set, and the
result is a score for a procedure nobody could have run.

THREE THINGS ARE DONE, AND THEY ARE NOT THE SAME THING.

    PURGE     drop every fitting index whose own outcome window overlaps a scoring index. This
              is about the TARGET's horizon and it is what most implementations stop at.
    EMBARGO   drop a further band immediately after the scoring block, because a fitting row
              just after it can carry information about the scoring rows through the features
              rather than through the target. Applied on BOTH sides, which is where
              implementations differ and where a property test earns its place.
    COUNT     report how many effectively independent observations are left, because two
              thousand rows at a twenty day horizon are not two thousand observations, and the
              headline of any control here is meaningless without that number.

The effective count is reported as the sample length divided by the horizon, which is the
crudest defensible answer and is stated as such. QUACKZ carries the argument about what a
dependent sample is worth in the deflated Sharpe setting; nothing here recomputes a QUACKZ
statistic, and this is a count rather than a statistic.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Split:
    """One fold. Both sides are index lists into the caller's own time-ordered frame."""

    fit: tuple[int, ...]
    score: tuple[int, ...]

    def __post_init__(self) -> None:
        if set(self.fit) & set(self.score):
            raise ValueError("an index appears in both the fitting and the scoring block")


def purged_splits(n_obs: int, *, horizon: int, embargo: int, folds: int = 5) -> list[Split]:
    """Contiguous scoring blocks, with the horizon purged and the embargo applied both sides.

    Raises rather than returning something degenerate when the parameters cannot produce a fold
    with anything in it. A splitter that silently returns an empty fitting set turns into a
    model scored against nothing, and the score it produces looks like a number.
    """
    if n_obs <= 0:
        raise ValueError("n_obs must be positive")
    if horizon < 0 or embargo < 0:
        raise ValueError("the horizon and the embargo are lengths, so neither can be negative")
    if folds < 2:
        raise ValueError("a single fold scores the whole sample it was fitted on")
    if n_obs < folds:
        raise ValueError(f"{n_obs} observations cannot be cut into {folds} blocks")

    edges = [round(index * n_obs / folds) for index in range(folds + 1)]
    splits: list[Split] = []
    for fold in range(folds):
        start, stop = edges[fold], edges[fold + 1]
        if start == stop:
            continue
        score = range(start, stop)

        # THE PURGE IS THE UNION OF EVERY SCORING ROW'S OWN WINDOW, not a band at the edges. A
        # scoring index at `i` has an outcome measured out to `i + horizon`, so a fitting index
        # anywhere in that span shares it.
        forbidden: set[int] = set()
        for index in score:
            forbidden.update(range(index - horizon, index + horizon + 1))
        # AND THE EMBARGO ON BOTH SIDES. After the block because a fitting row just past it is
        # nearly the same day; before it for the same reason in the other direction. An embargo
        # applied only after the block is the commonest form of this and it is asymmetric for no
        # stated reason.
        forbidden.update(range(start - horizon - embargo, start))
        forbidden.update(range(stop, stop + horizon + embargo))

        fit = tuple(index for index in range(n_obs) if index not in forbidden)
        splits.append(Split(fit=fit, score=tuple(score)))
    return splits


def effective_observations(n_obs: int, *, horizon: int) -> int:
    """How many independent observations a dependent sample is worth, stated crudely.

    Rows one day apart at a twenty day horizon share nineteen twentieths of their outcome. The
    honest count is not the row count, and this returns the row count divided by the horizon,
    floored at one. It is deliberately the crudest defensible answer: anything cleverer would be
    a statistic, and a statistic needs a paper behind it rather than a docstring.
    """
    if horizon <= 0:
        return n_obs
    return max(1, n_obs // horizon)
