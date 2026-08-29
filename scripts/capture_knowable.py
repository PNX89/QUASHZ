"""Recover when an observation first became available, by bisecting ALFRED vintages.

    uv run python scripts/capture_knowable.py

WHY THIS EXISTS. A feature dated the first of the quarter was not knowable on the first of the
quarter. Real GDP for the first quarter of 2024 carries the label 2024-01-01 and was first
published on 2024-04-25, so a model that used it to make a decision in January used a number
that did not exist. That gap is not a constant and it is not in any table shipped with the data:
it is recovered here, per observation, from the archive itself.

THE ENDPOINT, AND THE THREE WAYS IT LIES QUIETLY.

    https://alfred.stlouisfed.org/graph/alfredgraph.csv?id=SERIES&vintage_date=YYYY-MM-DD

1. `fred.stlouisfed.org/graph/fredgraph.csv` accepts `vintage_date` and IGNORES it, returning
   today's values with HTTP 200 under a bare `observation_date,SERIES` header. A bisection
   pointed at that host concludes every observation was knowable on its own reference date.
   Guarded by requiring the header to read `SERIES_YYYYMMDD`, which the ALFRED host returns.

2. A calendar date that is not a real vintage also returns HTTP 200, serving the nearest
   PRECEDING real vintage, under a header echoing the date that was asked for. The header is an
   echo rather than a report, so the check above cannot detect this at all. It is why the column
   below is called `probe_date` and not `vintage`, and why the final bracket is only accepted
   when the two probes return DIFFERENT content.

3. A vintage after the last one is clamped to the latest, and there the header does report the
   real date rather than the requested one. That is the only case where it tells the truth, and
   it is not one this bisection relies on.
"""

from __future__ import annotations

import csv
import datetime
import hashlib
import pathlib
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "quashz" / "data"
FIXTURES = ROOT / "tests" / "fixtures"

ALFRED = (
    "https://alfred.stlouisfed.org/graph/alfredgraph.csv"
    "?id={series}&cosd={start}&coed={end}&vintage_date={probe}"
)
WRONG_HOST = (
    "https://fred.stlouisfed.org/graph/fredgraph.csv"
    "?id={series}&cosd={start}&coed={end}&vintage_date={probe}"
)


#: What to recover, and why the quarterly series is recovered for EVERY quarter rather than for
#: an example.
#:
#: A lag measured on one observation is an anecdote. The frame needs to know, for every decision
#: date, which quarterly figure had been published by then, and the gap is not constant: it is
#: measured here at between 115 and 121 days for three consecutive quarters, and the whole point
#: of recovering it is that nothing in the data says which.
#:
#: DGS10 is the control. A daily series is supposed to be available almost at once, and this
#: measures whether it is rather than assuming a zero lag, which would be the same mistake in
#: the other direction.
def wanted() -> list[tuple[str, str, str, str]]:
    """Every quarter from 2015 to the last one the corpus holds, plus two daily spot checks."""
    import csv as _csv

    quarters: list[tuple[str, str, str, str]] = []
    with (DATA / "GDPC1.csv").open(encoding="utf-8", newline="") as handle:
        labels = [row["observation_date"] for row in _csv.DictReader(handle)]
    for label in labels:
        if label < "2015-01-01":
            continue
        start = datetime.date.fromisoformat(label)
        # A year of search space after the quarter starts. Every measured lag so far is under
        # 130 days, and a bracket that is too wide costs one extra probe rather than an answer.
        until = (start + datetime.timedelta(days=400)).isoformat()
        quarters.append(("GDPC1", label, label, until))
    return [
        *quarters,
        ("DGS10", "2024-01-02", "2024-01-02", "2024-03-31"),
        ("DGS10", "2024-06-03", "2024-06-03", "2024-08-31"),
    ]


PAUSE_SECONDS = 0.4


def probe(series: str, observation: str, when: str, url: str = ALFRED) -> tuple[str, str, str]:
    """One request. Returns the header, the data rows joined, and the SHA-256 of those rows.

    THE HASH IS OF THE ROWS WITH THE HEADER STRIPPED, and that is the whole point of it: the
    header carries the probe date, so hashing the whole response would make every probe unique
    and the bracket check would pass on any two dates at all.
    """
    request = urllib.request.Request(
        url.format(series=series, start=observation, end=observation, probe=when),
        headers={"User-Agent": "quashz-capture"},
    )
    time.sleep(PAUSE_SECONDS)
    with urllib.request.urlopen(request, timeout=90) as response:
        body = response.read().decode("utf-8")
    lines = [line for line in body.splitlines() if line.strip()]
    header, rows = lines[0], "\n".join(lines[1:])
    return header, rows, hashlib.sha256(rows.encode("utf-8")).hexdigest()


def present(rows: str, observation: str) -> bool:
    return any(line.startswith(f"{observation},") for line in rows.splitlines())


def recover(series: str, observation: str, first: str, last: str) -> dict[str, object]:
    """Bisect for the earliest probe date at which the observation is served at all."""
    lo = datetime.date.fromisoformat(first)
    hi = datetime.date.fromisoformat(last)
    probes = 0

    header, rows, digest = probe(series, observation, hi.isoformat())
    probes += 1
    if header != f"observation_date,{series}_{hi:%Y%m%d}":
        raise SystemExit(
            f"the archive returned the header {header!r} for a {hi} probe. A bare series id "
            f"means the request reached the host that ignores the vintage and answers with "
            f"today's data, and every result from here would be a fiction with a 200 beside it"
        )
    if not present(rows, observation):
        raise SystemExit(f"{series} {observation} is absent even from the {hi} vintage")

    absent_at, absent_digest = lo, None
    header, rows, absent_digest = probe(series, observation, lo.isoformat())
    probes += 1
    if present(rows, observation):
        raise SystemExit(
            f"{series} {observation} is already present at {lo}, so the bracket does not "
            f"contain the moment it appeared and the answer would be the start of the search"
        )

    present_at, present_digest = hi, digest
    while (present_at - absent_at).days > 1:
        middle = absent_at + (present_at - absent_at) / 2
        _, rows, digest = probe(series, observation, middle.isoformat())
        probes += 1
        if present(rows, observation):
            present_at, present_digest = middle, digest
        else:
            absent_at, absent_digest = middle, digest

    # THE BRACKET CHECK. Two adjacent probe dates that return byte-identical data rows have not
    # crossed a publication, so a boundary reported between them would be an artefact of the
    # endpoint serving the nearest preceding vintage rather than a date the publisher acted on.
    if absent_digest == present_digest:
        raise SystemExit(
            f"{series} {observation}: the probes at {absent_at} and {present_at} returned "
            f"identical data, so no publication happened between them"
        )

    label = datetime.date.fromisoformat(observation)
    return {
        "series": series,
        "observation": observation,
        "knowable_from": present_at.isoformat(),
        "last_probe_without_it": absent_at.isoformat(),
        "probes": probes,
        "days_from_the_observation_label": (present_at - label).days,
        "rows_digest_when_absent": absent_digest,
        "rows_digest_when_present": present_digest,
    }


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    FIXTURES.mkdir(parents=True, exist_ok=True)

    targets = wanted()
    print(f"recovering {len(targets)} observations")
    recovered = []
    for target in targets:
        try:
            recovered.append(recover(*target))
        except SystemExit as exc:
            print(f"  {target[0]} {target[1]}: SKIPPED, {exc}")
    for entry in recovered:
        print(
            f"  {entry['series']} {entry['observation']}: knowable from "
            f"{entry['knowable_from']}, {entry['days_from_the_observation_label']} days after "
            f"its label, {entry['probes']} probes"
        )

    with (DATA / "knowable_from.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "series",
                "observation",
                "knowable_from",
                "last_probe_without_it",
                "probes",
                "days_from_the_observation_label",
                "rows_digest_when_absent",
                "rows_digest_when_present",
            ],
        )
        writer.writeheader()
        writer.writerows(recovered)

    # THE NEGATIVE FIXTURE, committed rather than described. This is what the wrong host returns
    # for a request carrying a vintage: HTTP 200, a bare header, and current values. The offline
    # suite asserts the guard rejects it, which it cannot do against a paragraph.
    header, rows, _ = probe("GDPC1", "2024-01-01", "2024-04-24", url=WRONG_HOST)
    (FIXTURES / "wrong_host_ignores_the_vintage.csv").write_text(
        f"{header}\n{rows}\n", encoding="utf-8"
    )
    print(f"  negative fixture: the wrong host answered {header!r}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.URLError as exc:
        print(f"the archive could not be reached: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
