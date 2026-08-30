"""The corpus readers' own guards, exercised against a fixture the test writes itself.

`fed()` refuses a CSV whose header has moved, `ecb_reference_rate()` refuses a file missing a
required column, and it filters rows by KEY. All three sit on the read path for the committed
corpus and none of them was reachable from the files as committed, because the committed files
already satisfy every check. Only a broken file can prove a validation lives, so the fixture
here is deliberately broken, and that is legitimate: the object under test is the reader's
REACTION to a bad file, not a description of a good one.
"""

from __future__ import annotations

import datetime
import pathlib

import pytest

from quashz import corpus


def test_fed_refuses_a_csv_whose_header_has_moved(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The column position is the contract, not merely the column's presence."""
    monkeypatch.setattr(corpus, "DATA", tmp_path)
    (tmp_path / "DGS10.csv").write_text(
        "observation_date,YIELD\n2024-01-02,4.5\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="has moved"):
        corpus.fed("DGS10")


def test_ecb_reference_rate_refuses_a_file_missing_a_required_column(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TIME_PERIOD, OBS_VALUE and KEY are read by name, so a renamed one must be caught by name."""
    monkeypatch.setattr(corpus, "DATA", tmp_path)
    (tmp_path / "ECB_EXR_D_USD_EUR_SP00_A.csv").write_text(
        "TIME_PERIOD,OBS_VALUE\n2024-01-02,1.10\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="KEY"):
        corpus.ecb_reference_rate()


def test_ecb_reference_rate_keeps_only_the_series_the_licence_names(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A no-op on the committed file, which holds one KEY, is still a real filter on a bigger one.

    The committed file happens to carry a single distinct KEY, so this filter has never dropped a
    row in this repository. That is a fact about today's file, not about the reader, and the only
    way to tell the two apart is a fixture that carries a second KEY.
    """
    monkeypatch.setattr(corpus, "DATA", tmp_path)
    (tmp_path / "ECB_EXR_D_USD_EUR_SP00_A.csv").write_text(
        "TIME_PERIOD,OBS_VALUE,KEY\n"
        "2024-01-02,1.10,EXR.D.USD.EUR.SP00.A\n"
        "2024-01-02,1.20,EXR.D.GBP.EUR.SP00.A\n"
        "2024-01-03,1.11,EXR.D.USD.EUR.SP00.A\n",
        encoding="utf-8",
    )
    values = corpus.ecb_reference_rate()
    assert values == {
        datetime.date(2024, 1, 2): 1.10,
        datetime.date(2024, 1, 3): 1.11,
    }
