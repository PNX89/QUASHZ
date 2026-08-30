"""A splitter that puts the horizon between the block fitted on and the block scored on.

WHY THE ORDINARY ONE IS WRONG HERE. A row's outcome is measured over the following twenty
trading days, so two rows twenty days apart share nineteen days of the same future. Shuffling
them into different folds puts most of a scoring row's answer into the fitting set, and the
result is a score for a procedure nobody could have run.

THREE THINGS ARE DONE, AND THEY ARE NOT THE SAME THING.

    PURGE     drop every fitting index whose own outcome window overlaps a scoring index. This
              is about the TARGET's horizon and it is what most implementations stop at.
    EMBARGO   drop a further band BEYOND the purged window, because a fitting row just past
              the horizon can still carry information about the scoring rows through the
              features rather than through the target. Applied on BOTH sides, which is where
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
        # UNREACHABLE GIVEN THE GUARD ABOVE, AND ASSERTED RATHER THAN SWALLOWED. `n_obs >=
        # folds` keeps every unrounded step at least 1, and a brute force search over folds 2
        # to 29 and n_obs up to 20,000 never rounded two consecutive edges to the same index. A
        # `continue` here would silently drop a fold and break the tiling property the property
        # test asserts; an assertion fails loudly the day a change to the edge formula makes it
        # reachable instead of hiding a fold that went missing.
        assert start != stop, f"fold {fold} of {folds} produced an empty scoring block"
        score = range(start, stop)

        # THE PURGE IS THE UNION OF EVERY SCORING ROW'S OWN WINDOW, not a band at the edges. A
        # scoring index at `i` has an outcome measured out to `i + horizon`, so a fitting index
        # anywhere in that span shares it.
        forbidden: set[int] = set()
        for index in score:
            forbidden.update(range(index - horizon, index + horizon + 1))
        # AND THE EMBARGO ON BOTH SIDES, EACH BAND STARTING WHERE THE PURGE ENDS. After the
        # block because a fitting row just past the horizon is nearly the same day; before it
        # for the same reason in the other direction. An embargo applied only after the block is
        # the commonest form of this and it is asymmetric for no stated reason.
        #
        # THE BOUNDS ARE WRITTEN AS THE PURGE PLUS A BAND rather than as a band reaching back to
        # the block, and the two produce the same set. Writing them from the block made the loop
        # above contribute nothing except the scoring indices themselves: on a contiguous block
        # its union is the block widened by the horizon, and both tails of that already sat
        # inside these bands. Deleting the horizon from the purge changed no output and failed
        # no test, so the guarantee this splitter exists for was covered by the embargo and
        # nothing was watching it.
        forbidden.update(range(start - horizon - embargo, start - horizon))
        forbidden.update(range(stop + horizon, stop + horizon + embargo))

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
