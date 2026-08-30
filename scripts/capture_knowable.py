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
import re
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
def wanted(today: datetime.date | None = None) -> list[tuple[str, str, str, str]]:
    """Every quarter from 2015 to the last one the corpus holds, plus two daily spot checks.

    THE SEARCH WINDOW ENDS TODAY AND THE CLOCK IS AN ARGUMENT SO THIS CAN BE CHECKED. It used
    to end at the label plus 400 days for every quarter, whether or not that day had happened.
    For any quarter labelled inside the last 400 days that is a vintage the archive cannot have,
    the first probe of the bisection asks for it, the archive clamps the request to its latest
    real vintage and reports THAT date in the header, and the guard below correctly refuses a
    reply about a day nobody asked about. Three quarters the corpus already holds values for
    were dropped that way, and the committed file records none of it.
    """
    import csv as _csv

    today = today or datetime.date.today()
    quarters: list[tuple[str, str, str, str]] = []
    with (DATA / "GDPC1.csv").open(encoding="utf-8", newline="") as handle:
        rows = [(row["observation_date"], row["GDPC1"]) for row in _csv.DictReader(handle)]
    for label, value in rows:
        if label < "2015-01-01":
            continue
        start = datetime.date.fromisoformat(label)
        # A quarter that has not begun, and one the publisher has written a full stop against,
        # were both never served, so there is no publication date to look for. Skipped here,
        # where it is one line of arithmetic, rather than by a refusal fifty probes later that
        # now stops the whole run.
        if start >= today or value.strip() in ("", "."):
            continue
        # A year of search space after the quarter starts, and never past the day this is run.
        # Every measured lag so far is under 130 days, so a bracket that is too wide costs one
        # extra probe rather than an answer, and one that ends in the future costs the quarter.
        until = min(start + datetime.timedelta(days=400), today).isoformat()
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


#: What a reply from the archive looks like when it is answering about a real vintage: the
#: series id carrying that vintage's own date. Whether it is the date that was ASKED for is a
#: separate question, and the two answers have different causes.
ARCHIVE_HEADER = re.compile(r"^observation_date,(?P<series>[A-Za-z0-9]+)_(?P<vintage>\d{8})$")


def refuse_a_reply_that_is_not_from_the_archive(
    header: str, series: str, probe_date: datetime.date
) -> None:
    """The one check standing between this bisection and a confident fiction.

    IT LIVES IN A FUNCTION OF ITS OWN BECAUSE OF WHERE IT USED TO LIVE. This was four lines
    inside `recover`, reachable only by making a network request, so the only way to see it
    reject anything was to point the script at the wrong host and watch. The committed fixture
    beside this file was captured for exactly that purpose and then read by nothing: the comment
    that writes it says the offline suite asserts the guard rejects it, and no test imported
    this module at all. A guard nobody has watched refuse is a guard nobody has tested.

    What it detects: `fredgraph.csv` accepts `vintage_date`, ignores it, and answers 200 with
    today's numbers under a bare `observation_date,SERIES` header. The archive answers under
    `observation_date,SERIES_YYYYMMDD`. The suffix is the whole difference between a vintage and
    a fiction, and it is the reason a wrong-host bisection concludes that every observation was
    knowable on its own reference date.

    What it does NOT detect, said here rather than assumed: a calendar date that is not a real
    vintage also answers 200, serving the nearest preceding real vintage under a header that
    ECHOES the date asked for. This check passes on that reply, which is why the column is named
    `probe_date` and why a bracket is accepted only when two probes return different content.

    TWO REFUSALS, BECAUSE THERE ARE TWO CAUSES AND THEY ARE FIXED DIFFERENTLY. A probe past the
    last vintage the archive holds is clamped to the latest, and there the header reports the
    real date instead of echoing the request. That reply is well formed and from the right host:
    the request was simply for a day the archive cannot answer about, and the caller's search
    window is what has to change. Blaming the wrong host for it sent the reader looking at a URL
    that was correct, which is how three quarters stayed missing.
    """
    if header == f"observation_date,{series}_{probe_date:%Y%m%d}":
        return
    served = ARCHIVE_HEADER.match(header)
    if served is not None and served["series"] == series:
        raise SystemExit(
            f"the archive answered a {probe_date} probe with its {served['vintage']} vintage. A "
            f"date after the last vintage it holds is clamped to the latest one, and there the "
            f"header reports the real date rather than echoing the request, so this probe is "
            f"off the end of the archive rather than at the host that ignores the vintage"
        )
    raise SystemExit(
        f"the archive returned the header {header!r} for a {probe_date} probe. A bare series "
        f"id means the request reached the host that ignores the vintage and answers with "
        f"today's data, and every result from here would be a fiction with a 200 beside it"
    )


def recover(series: str, observation: str, first: str, last: str) -> dict[str, object]:
    """Bisect for the earliest probe date at which the observation is served at all."""
    lo = datetime.date.fromisoformat(first)
    hi = datetime.date.fromisoformat(last)
    probes = 0

    header, rows, digest = probe(series, observation, hi.isoformat())
    probes += 1
    refuse_a_reply_that_is_not_from_the_archive(header, series, hi)
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
    skipped: list[str] = []
    for target in targets:
        try:
            recovered.append(recover(*target))
        except SystemExit as exc:
            skipped.append(f"{target[0]} {target[1]}")
            print(f"  {target[0]} {target[1]}: SKIPPED, {exc}")

    # A PARTIAL RECOVERY IS NEVER WRITTEN OVER A COMPLETE ONE, and the shell is told. Every skip
    # went to a stdout nobody keeps, the survivors were written out, and the exit code was zero,
    # so three quarters the corpus holds values for left the committed file with nothing
    # anywhere recording that they had ever been asked for.
    if skipped:
        print(
            f"{len(skipped)} of {len(targets)} targets were skipped, so this recovery is "
            f"partial and nothing was written: {', '.join(skipped)}",
            file=sys.stderr,
        )
        return 1

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
    # for a request carrying a vintage: HTTP 200, a bare header, and current values. It is read
    # by tests/test_wrong_host.py, which feeds this exact first line to the guard and requires
    # a refusal. The claim that it was read used to be made here and be false.
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
