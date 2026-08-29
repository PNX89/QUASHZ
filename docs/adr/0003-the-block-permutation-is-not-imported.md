# 3. The block permutation is written here, not imported from a sibling

Accepted, 29 August 2026.

## Context

A sibling repository, QUACKZ, owns the block-resampling machinery in this toolset: a Politis and
Romano stationary bootstrap, a Sharpe ratio, a deflated Sharpe and a trial-deflation table. The
build plan for this repository said to import the block primitive from there rather than write
another one, under a test forbidding the reimplementation of a QUACKZ statistic. That instinct is
right and the literal instruction turned out to be wrong.

## Decision

Write the circular block permutation here, and keep the rule that produced the instruction.

**They are different objects.** A stationary bootstrap draws blocks of geometric length WITH
replacement to build a sampling distribution for a statistic. What is needed here is a
permutation of contiguous blocks WITHOUT replacement, to destroy the pairing between features and
target while leaving the target's own serial structure intact. Using the first to do the second
would run, and every null it produced would be of the wrong thing.

**The mechanics of importing it are also bad.** QUACKZ is not published, no repository in this
set depends on another, and the only block primitive it has is a private name. A git dependency
on another repository's default branch would make this repository's build fail on a change
nobody made here.

## Consequences

The rule survives with sharper teeth than a naming convention. `tests/test_no_sibling_statistic`
asserts that this repository contains no Sharpe ratio, no deflated Sharpe, no stationary
bootstrap and no trial-deflation table, which are the four things QUACKZ owns. The effective
observation count is linked to QUACKZ in the README rather than recomputed with a different
justification.

The permutation written here was wrong in its first form and the property test found it: cutting
from fixed starts and wrapping each block with a modulo is not a bijection when the block length
does not divide the sample, and at ten observations with a block length of four it returned two
indices twice and dropped two others. The bijection is now a property over every shape.
