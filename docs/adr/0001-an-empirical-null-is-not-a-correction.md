# 1. An empirical null is not a multiple comparisons correction

Accepted, 29 August 2026.

## Context

The verdict reports where a candidate's score sits inside a distribution built by permuting the
target 200 times. It is easy to read that as a correction for having tried several things, and
it is not one. The two answer different questions and confusing them is the kind of error that
survives review because both sound careful.

## Decision

The empirical null answers: **under the hypothesis that the features carry nothing about the
target, how often does a score this high arise?** It is calibration of one statistic against one
hypothesis, using the data's own dependence structure rather than a textbook distribution that
assumes independence this sample does not have.

It says nothing whatever about how many hypotheses were tried. Two estimator families are run
here, so two scores are produced, and no adjustment is made for that anywhere. If a reader wants
a family-wise statement, this repository does not provide one and does not pretend to.

The distinction is stated in the README, in the harness transcript, and in `controls.py` where
the code lives, because a reader who meets it in only one of those three places has met an
assurance rather than an argument.

## Consequences

The reported `empirical_p` is a per-hypothesis quantity. Reading it as though it were corrected
would overstate what was measured, and reading it as meaningless because it is uncorrected would
understate it: a score outside the range of 200 block permutations of its own target is still a
fact about this frame.

The convention is `(rank + 1) / (n + 1)`, so it can never return zero. A finite ensemble cannot
support a claim of zero, and a p of 0.0000 printed from 200 draws is a presentation choice
pretending to be a result.
