"""The recovery script's own arithmetic, checked without reaching the archive.

WHY THESE ARE OFFLINE TESTS OF A NETWORK SCRIPT. Three defects compounded into one silent
truncation of the committed corpus, and not one of them was in the bisection. The search window
ended at the label plus 400 days whether or not that day had happened; the guard blamed the
wrong host for a reply that was in fact well formed and from the right one; and `main` caught
every refusal, printed it to a stdout nobody keeps, wrote the survivors over the complete file
and returned zero. All three are decidable from a calendar and a stub, which is why they are
here in the offline suite rather than in the manual workflow that reaches live publishers.
"""

from __future__ import annotations

import datetime
import pathlib
import sys
from typing import Any

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import capture_knowable  # noqa: E402

#: A day the corpus is behind, so `wanted()` is asked about a fixed calendar rather than today's.
WHEN = datetime.date(2026, 8, 30)


def test_no_target_asks_the_archive_for_a_vintage_that_has_not_happened() -> None:
    """The defect that emptied three quarters out of the committed file.

    A probe for a vintage after the last one the archive holds is answered 200, clamped to the
    latest real vintage, under a header reporting THAT date. The guard refuses it, correctly,
    and the quarter is lost. Every quarter labelled inside the last 400 days was asked for that
    way, which is exactly the recent end of the corpus and the end the frame is thinnest at.
    """
    targets = capture_knowable.wanted(WHEN)
    unaskable = [target for target in targets if target[3] > WHEN.isoformat()]
    assert unaskable == [], (
        f"these targets end their search after the day the capture runs, so their first probe "
        f"asks for a vintage that does not exist yet: {unaskable}"
    )


def test_the_window_is_clamped_rather_than_the_quarter_dropped() -> None:
    """The other half, and the half a careless fix would break.

    Narrowing the window is the fix. Skipping the quarters that needed it would satisfy the test
    above perfectly and leave the corpus exactly as truncated as it was, so what is asserted here
    is that every quarter the corpus holds a figure for is still asked about.
    """
    import csv

    with (capture_knowable.DATA / "GDPC1.csv").open(encoding="utf-8", newline="") as handle:
        held = {
            row["observation_date"]
            for row in csv.DictReader(handle)
            if row["observation_date"] >= "2015-01-01"
            and row["observation_date"] < WHEN.isoformat()
            and row["GDPC1"].strip() not in ("", ".")
        }
    asked = {target[1] for target in capture_knowable.wanted(WHEN) if target[0] == "GDPC1"}
    assert held - asked == set(), (
        f"the corpus holds a figure for these quarters and the capture never asks the archive "
        f"when they were published: {sorted(held - asked)}"
    )


def test_a_probe_past_the_last_vintage_is_refused_as_the_clamp_it_is() -> None:
    """One guard, two causes, and they are fixed in different files.

    A clamped reply carries a real vintage suffix for a real day. Reporting it as the host that
    ignores `vintage_date` sends the reader to check a URL that was correct all along, and the
    thing that actually has to change is the caller's search window.
    """
    with pytest.raises(SystemExit) as refusal:
        capture_knowable.refuse_a_reply_that_is_not_from_the_archive(
            "observation_date,GDPC1_20260830", "GDPC1", datetime.date(2026, 11, 5)
        )
    message = str(refusal.value)
    assert "clamped" in message, f"the refusal does not name the clamp: {message}"
    assert "20260830" in message, "the refusal does not say which vintage was actually served"
    assert "bare series" not in message, (
        "a clamped reply is still being reported as the host that ignores the vintage, which is "
        "a different host, a different fix and a different file"
    )


def one_target(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> pathlib.Path:
    """Point the script at a scratch directory holding one already complete recovery."""
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(capture_knowable, "DATA", data)
    monkeypatch.setattr(capture_knowable, "FIXTURES", tmp_path / "fixtures")
    monkeypatch.setattr(
        capture_knowable, "wanted", lambda *_: [("GDPC1", "2026-04-01", "2026-04-01", "2026-08-30")]
    )
    complete = data / "knowable_from.csv"
    complete.write_text("series,observation\nGDPC1,2015-01-01\n", encoding="utf-8")
    return complete


def test_a_partial_recovery_is_not_written_over_a_complete_one(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The failure that made the other two invisible.

    A refusal was caught, printed, and then everything that had survived it was written over the
    committed file with an exit code of zero beside it. Nothing on disk recorded that a target
    had ever been asked for, so no reader and no test could see that three were missing.
    """
    complete = one_target(monkeypatch, tmp_path)
    before = complete.read_text(encoding="utf-8")

    def refuse(*_: object) -> Any:
        raise SystemExit("the archive answered a 2026-11-05 probe with its 20260830 vintage")

    def unreachable(*_: object, **__: object) -> Any:
        raise AssertionError("main() reached the network after a target was skipped")

    monkeypatch.setattr(capture_knowable, "recover", refuse)
    monkeypatch.setattr(capture_knowable, "probe", unreachable)

    assert capture_knowable.main() != 0, "a partial recovery reported success to the shell"
    assert complete.read_text(encoding="utf-8") == before, (
        "a run that recovered nothing rewrote the committed file anyway"
    )


def test_a_complete_recovery_is_still_written(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A guard that refuses every run is an outage rather than a guard.

    The positive control for the refusal above, and it is not decoration: the check that stops a
    partial write sits between the recovery and the only two lines in this script that write
    anything, so a mistake in it stops the capture from ever succeeding.
    """
    complete = one_target(monkeypatch, tmp_path)

    def recovered(series: str, observation: str, *_: object) -> dict[str, object]:
        return {
            "series": series,
            "observation": observation,
            "knowable_from": "2026-07-30",
            "last_probe_without_it": "2026-07-29",
            "probes": 11,
            "days_from_the_observation_label": 120,
            "rows_digest_when_absent": "a" * 64,
            "rows_digest_when_present": "b" * 64,
        }

    monkeypatch.setattr(capture_knowable, "recover", recovered)
    monkeypatch.setattr(
        capture_knowable, "probe", lambda *_, **__: ("observation_date,GDPC1", "2024-01-01,1.0", "")
    )

    assert capture_knowable.main() == 0
    written = complete.read_text(encoding="utf-8").splitlines()
    assert written[0].startswith("series,observation,knowable_from")
    assert written[1].startswith("GDPC1,2026-04-01,2026-07-30")
