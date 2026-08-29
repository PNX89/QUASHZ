"""The committed reply from the host that ignores the vintage, fed to the guard that refuses it.

WHY THIS FILE EXISTS AT ALL. `scripts/capture_knowable.py` captured a negative fixture, wrote it
into `tests/fixtures/`, and said in a comment that the offline suite asserted the guard rejects
it. The offline suite did not: nothing in this repository read that file, and no test imported
the script. The fixture was a screenshot of a refusal rather than a refusal.

The refusal is worth testing rather than describing because of what it prevents. ALFRED and FRED
serve the same shaped CSV from nearly the same URL, both answer 200, and only one of them honours
`vintage_date`. A bisection pointed at the wrong one does not fail: it succeeds, and reports that
every observation was knowable on the day it is dated, which is exactly the belief this whole
repository exists to take apart.
"""

from __future__ import annotations

import datetime
import importlib.util
import pathlib
import sys
from typing import Any

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "wrong_host_ignores_the_vintage.csv"


def capture_knowable() -> Any:
    """Load the script as a module.

    It is a script rather than a package module, so it is loaded by path. The alternative was to
    copy the header rule into the test, and a test carrying its own copy of the thing it checks
    passes after the original is deleted.
    """
    path = ROOT / "scripts" / "capture_knowable.py"
    spec = importlib.util.spec_from_file_location("capture_knowable", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["capture_knowable"] = module
    spec.loader.exec_module(module)
    return module


def test_the_wrong_host_reply_is_refused() -> None:
    """The fixture's own first line, not a line typed here to look like it."""
    header = FIXTURE.read_text(encoding="utf-8").splitlines()[0]
    with pytest.raises(SystemExit) as refusal:
        capture_knowable().refuse_a_reply_that_is_not_from_the_archive(
            header, "GDPC1", datetime.date(2024, 4, 24)
        )
    assert "fiction with a 200 beside it" in str(refusal.value)
    assert header in str(refusal.value), (
        "the refusal does not quote what it received, so somebody reading the failure has to "
        "guess which host answered"
    )


def test_the_real_archive_reply_is_accepted() -> None:
    """A guard that refuses everything is not a guard, it is an outage."""
    capture_knowable().refuse_a_reply_that_is_not_from_the_archive(
        "observation_date,GDPC1_20240424", "GDPC1", datetime.date(2024, 4, 24)
    )


def test_the_date_in_the_header_has_to_be_the_date_that_was_asked_for() -> None:
    """Not merely SOME suffix, which a looser check would accept.

    A reply carrying a real vintage suffix for a different day is still the wrong answer, and
    matching on the shape rather than on the value would let it through.
    """
    with pytest.raises(SystemExit):
        capture_knowable().refuse_a_reply_that_is_not_from_the_archive(
            "observation_date,GDPC1_20240425", "GDPC1", datetime.date(2024, 4, 24)
        )


def test_the_fixture_is_what_the_wrong_host_actually_returns() -> None:
    """If the fixture were recaptured from the right host it would stop being a negative one.

    That failure is silent: the two tests above would still pass, because they would be feeding
    an accepted header to a guard that accepts it. So the fixture is checked for the property
    that makes it a fixture, a header with NO vintage suffix, and for real values under it.
    """
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "observation_date,GDPC1", (
        f"the fixture's header is {lines[0]!r}, which carries a vintage, so it is no longer a "
        f"reply from the host that ignores them"
    )
    reference, value = lines[1].split(",")
    assert datetime.date.fromisoformat(reference) == datetime.date(2024, 1, 1)
    assert float(value) > 0
