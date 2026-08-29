# QUASHZ

**A vendor sends a dataset. The first row this refuses is one whose OUTCOME had not been decided
yet when the decision would have been made, which is the refusal no data contract can express,
because no data pipeline has a target.**

[![CI](https://github.com/PNX89/QUASHZ/actions/workflows/ci.yml/badge.svg)](https://github.com/PNX89/QUASHZ/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

![A real run: 43 recovered publication dates, which quarterly figure a decision on 24 April 2024
could honestly have used, and the twenty days at the end of the corpus where a decision is
possible and supervision is not.](docs/demo.svg)

Of the days in this corpus where a model could have RUN, 2,828 of them, only 2,808 are days it
could have LEARNED from. The other 20 are not a data quality problem to be fixed. They are the
days nearest the present, where a decision is possible and supervision is not, and a build that
quietly trains on them is scoring itself on an answer it would not have had.

<!-- quoted from docs/evidence/verdict/the-verdict.txt -->
```text
ADMITTED   2808 rows
REFUSED    4123 rows, 59.5% of everything considered
             4103  no quarterly figure published by the decision date
               20  outcome not decidable at the decision date
```

One file to start with: [`src/quashz/frame.py`](src/quashz/frame.py). It names the three clocks
that have to be kept apart, and every refusal it issues is joined by a test to the archive that
measured the dates behind it.

## When each number actually existed, recovered rather than assumed

A figure dated the first of the quarter was not knowable on the first of the quarter. Real GDP
labelled 2024-01-01 was first served on 2024-04-25, 115 days later, and nothing in the data says
so. `scripts/capture_knowable.py` recovers it by bisecting the archive's vintage dates: 478
probes across 43 quarters, plus two daily checks that measure the yields' own release lag rather
than assuming it is zero.

**The lag is not a constant, which is the whole reason this cannot be a table.** 41 of the 43
quarters were first served between 115 and 121 days after the day they are labelled. The other
two took 150 and 175. This repository records when, not why: the archive answers the first
question and not the second.

What that costs a pipeline that reads a figure at its label date instead: **on 2,661 of the
2,808 decision dates, 94.8 per cent, it reads a number the publisher had not published yet**, by
up to 175 days.

**The archive lies in three ways and two of them return HTTP 200.** The wrong host accepts a
vintage, ignores it, and answers with today's values under a bare header. A date that is not a
real vintage also answers 200, serving the nearest preceding one, under a header **echoing the
date that was asked for**, so the header is an echo rather than a report and cannot detect it.
That is why the recovered column is called `probe_date`, and why a bracket is accepted only when
its two probes return different content.

## Two publishers of one number, and what they disagree about

A candidate series is admitted only after it is reconciled against an incumbent covering the
same quantity. The cases worth shipping are the ones where the two disagree and neither is wrong.

<!-- quoted from docs/evidence/reconciliation/two-publishers.txt -->
```text
  days both publish            651
  days they agree exactly      10
  median absolute difference   0.0015
  standard deviation           0.00187
  largest difference           0.0151
  days only the ECB publishes  23
  days only the Fed publishes  11
```

The two rates are fixed at different times of day from different panels. A rule demanding
equality rejects a good series; a rule with no tolerance at all accepts a stale one. Each
publisher also has days the other does not, and a naive join drops them and calls what is left
an overlap.

The same publisher's ten year yield, two year yield and the spread between them give a third
check that needs no second source. Over 12,557 days it holds on **12,554** and fails on **3**,
each off by two hundredths. Those three are committed rather than filtered, because a tolerance
tuned until nothing fails has been tuned to the sample it was tested on.

## The verdict, and what it is careful not to say

<!-- quoted from docs/evidence/verdict/the-verdict.txt -->
```text
--- logistic regression ---
  observed AUC 0.6206, rank 0 of 200, empirical p 0.0050
  smallest effect found at the declared rate: 0.8 standard deviations
--- histogram gradient boosting ---
  observed AUC 0.5886, rank 1 of 200, empirical p 0.0100
  smallest effect found at the declared rate: 1.6 standard deviations
```

**The negative control is an ensemble, not a draw.** One permuted fit gives one number, and one
number locates nothing. The target is permuted 200 times and the candidate's score is reported
as its rank inside that empirical null, with the whole distribution kept. The permutation is of
contiguous BLOCKS of a rotated index: shuffling a target row by row destroys its own serial
structure as well as its pairing with the features, which builds a null for an easier problem
than the real one.

**The positive control is a sweep, not a binary.** An effect of known size is planted and the
detection rate recorded across a grid, so the headline is the SMALLEST effect the procedure
caught rather than the assertion that it can catch something.

**Both estimator families are run and a disagreement would be recorded rather than resolved.**
Picking the family that agrees with what was wanted is the failure this whole repository is for.

**2,808 rows at a twenty day horizon are 140 effectively independent observations.** Every
number above is worth what that number says it is worth.

These controls bound what this procedure could have detected on this frame at the effect sizes
swept. They establish no absence of anything, and an empirical null is not a multiple
comparisons correction: it says where one score sits under one hypothesis and nothing about how
many were tried.

## What the vendor is handed

The rule that decides admission is one SQL statement, and every refused row lands in a ledger
with a reason in three columns. There is no severity column, because a severity column is a
request to ignore the rows below a threshold.

The artefact that goes back to the vendor is a Soda contract, executed against the file where it
already sits, and it has been watched failing as well as passing:

<!-- quoted from docs/evidence/contract/both-directions.txt -->
```text
$ soda contract verify   # the same frame with a vendor's mistake in it
#   one decision date duplicated, one slope removed
```

5 checks pass on the admitted frame; the same 5 run against a copy carrying what a vendor file
carries when it is wrong, and two of them fail. Their own engineer runs the same command against
their own copy and gets the same table, which is what an argument about a data problem needs.

Soda 4 rather than the 3.x line that carries SodaCL, and not by preference: 3.x is frozen at a
release pinning `duckdb<1.1.0` that declares no `requires-python` at all.

## Run it

The demo and the offline suite need nothing but Python and the committed corpus:

```text
uv run python examples/what_was_knowable.py
uv run pytest
```

Everything that needs a measuring instrument is separate, and each has its own CI job:

```text
uv run --group verdict pytest tests_verdict -q
uv run --group verdict python scripts/measure_verdict.py
uv run python scripts/measure_reconciliation.py
uv run --group verdict --group contract python scripts/measure_contract.py
```

Each rewrites its own directory under [`docs/evidence/`](docs/evidence), and CI runs all of them
and fails if a byte of the result changed, transcripts included. The capture scripts are not run
by any required job: they reach live publishers, and a build that goes red because somebody
else's service is down teaches people to ignore red builds.

## What this does not do

It does not say the data is clean, and it does not say a relationship exists. It says what this
procedure could have found at a stated effect size on one frame of 140 effective observations.

It does not model a market and nothing here was traded on. The target is a direction over a
twenty day horizon, chosen because it is a target whose outcome is not always decidable, which
is the property the refusal needs.

It recovers publication dates for one quarterly series and two daily ones, back to 2015. Of the
4,123 rows refused in total, 4,103 are refused for exactly that reason: they fall before the
first recovered publication date, and inventing an earlier one is precisely the mistake this
exists to catch.

<!-- toolset:start -->

Part of the Q...Z toolset, all of it designing for the failure that does not announce itself:

- [QUACKZ](https://github.com/PNX89/QUACKZ), deflating a backtest that only looks good because
  it was picked out of two hundred.
- [QUOTEZ](https://github.com/PNX89/QUOTEZ), market data an agent can read and cannot act on.
- [QUELLZ](https://github.com/PNX89/QUELLZ), measuring what prompt-injection containment costs
  in utility as well as in attack rate.
- [QUIDZ](https://github.com/PNX89/QUIDZ), refusing the outbound payment that would have gone
  out twice.
- [QUESTZ](https://github.com/PNX89/QUESTZ), stopping a scraper before it writes a CSV from a
  page that changed shape.
- [QUIZZ](https://github.com/PNX89/QUIZZ), answering what a statistic said at the time, and
  refusing when it cannot.
- [QUARANTINEZ](https://github.com/PNX89/QUARANTINEZ), treating an outcome the venue never
  confirmed as terminal rather than as a retry.
- [QUENCHZ](https://github.com/PNX89/QUENCHZ), deciding in the open what a tool server gets free
  while it is still somebody's subprocess.
- [QUILTZ](https://github.com/PNX89/QUILTZ), proving infrastructure code wrong without a cloud
  account, and saying what that cannot show.
- [QUAYZ](https://github.com/PNX89/QUAYZ), telling a crash loop from an OOMKill, and naming the
  failure that no single field finds.
- [QUARRYZ](https://github.com/PNX89/QUARRYZ), keeping every version a statistical office
  published, and failing the build when it quietly issues another.
- QUASHZ, this one: refusing a row whose outcome had not been decided yet when the decision
  would have been made.

**On QUACKZ.** QUACKZ owns the block resampling machinery in this set, and the build plan for
this repository said to import it. That turned out to be wrong for a reason worth stating: a
stationary bootstrap draws geometric blocks with replacement to build a sampling distribution,
and what is needed here is contiguous blocks without replacement to destroy a pairing while
leaving the target's own serial structure intact. Using one for the other would run, and every
null it produced would be of the wrong thing. The rule survives as a test asserting this
repository names no statistic that one owns.

<!-- toolset:end -->

## Development

```text
uv sync --dev
uv run pytest
uv run ruff check .
uv run mypy .
```

## Licence

MIT for the code. The Federal Reserve and Bureau of Economic Analysis series are United States
government work. The European Central Bank series is redistributed under terms that permit no
modification of the data or its metadata, so its file is committed exactly as served, all 32
columns of it, and every normalisation happens at read time.
