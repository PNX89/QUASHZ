"""Reading the committed corpus, including the file that may not be tidied.

Every publisher here is read at run time rather than at capture time, because one of them
forbids modifying what was served. The ECB permits reuse only WITHOUT modification, metadata
included, so `src/quashz/data/ECB_EXR_D_USD_EUR_SP00_A.csv` is committed with all 32 of its
columns exactly as the Data Portal returned them. Two of those columns are the data. The other
thirty are the price of using it honestly, and normalising them into a tidy two-column file
would be the modification the licence rules out.
"""

from __future__ import annotations

import csv
import datetime
import json
import pathlib
from typing import Any

DATA = pathlib.Path(__file__).resolve().parent / "data"

#: The value the Federal Reserve writes for a day it published no number on.
MISSING = "."


def source() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((DATA / "SOURCE.json").read_text(encoding="utf-8"))
    return loaded


def fed(series: str) -> dict[datetime.date, float]:
    """One Federal Reserve or BEA series, as a date to value mapping.

    Days the publisher marked with a full stop are DROPPED rather than carried as a null or
    filled forward. A holiday is not a day with an unknown yield, it is a day with no yield,
    and a frame that fills it forward invents an observation the publisher never made.
    """
    values: dict[datetime.date, float] = {}
    with (DATA / f"{series}.csv").open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["observation_date", series]:
            raise ValueError(f"{series}.csv has the header {reader.fieldnames}, which has moved")
        for row in reader:
            raw = row[series]
            if raw == MISSING or not raw.strip():
                continue
            values[datetime.date.fromisoformat(row["observation_date"])] = float(raw)
    return values


def ecb_reference_rate() -> dict[datetime.date, float]:
    """The ECB file, normalised HERE rather than in the committed bytes.

    The two columns that matter are TIME_PERIOD and OBS_VALUE. The other thirty travel with them
    because the licence says they must, and this function is the only place that ignores them.
    """
    values: dict[datetime.date, float] = {}
    path = DATA / "ECB_EXR_D_USD_EUR_SP00_A.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        for required in ("TIME_PERIOD", "OBS_VALUE", "KEY"):
            if required not in fields:
                raise ValueError(f"the ECB file has no {required} column: {fields}")
        for row in reader:
            if row["KEY"] != "EXR.D.USD.EUR.SP00.A":
                continue
            values[datetime.date.fromisoformat(row["TIME_PERIOD"])] = float(row["OBS_VALUE"])
    return values


def knowable_from() -> list[dict[str, str]]:
    """What the archive said about when each recovered observation first existed."""
    with (DATA / "knowable_from.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
