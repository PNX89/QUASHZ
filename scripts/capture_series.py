"""Capture the committed corpus from the publishers, once, so every measurement runs offline.

    uv run python scripts/capture_series.py

WHAT IS CAPTURED AND WHY EACH ONE IS HERE.

    DGS10, DGS2, T10Y2Y   Federal Reserve H.15. Two constant-maturity Treasury yields and the
                          spread the Fed publishes between them, which is the reconciliation
                          case where a derived series can be checked against its own inputs.
    DEXUSEU               Federal Reserve H.10, the dollar per euro rate, which the ECB also
                          publishes for the same days from its own fixing.
    GDPC1                 Bureau of Economic Analysis real GDP, the series whose value for a
                          quarter is not published until months after the quarter it is about.

LICENCE, AND THE ONE PLACE IT CHANGES THE CODE. The Federal Reserve and BEA series are United
States government work and are reproduced here freely. The ECB's reuse policy permits
redistribution only WITHOUT modification, including of the metadata, so the ECB file is written
byte for byte as the ECB served it: all 32 of its columns, its own header, its own ordering.
Nothing here prunes it, renames it or reformats it, and every normalisation happens at read
time in `quashz.corpus`. A committed file that has been tidied is a modified file.

NOTHING HERE RUNS IN A REQUIRED CI JOB. This reaches the live publishers, so it belongs to the
one manually triggered workflow that is allowed to fail. Every required job reads what this
already wrote.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import pathlib
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "quashz" / "data"

FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
ECB = (
    "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A"
    "?format=csvdata&startPeriod=2024-01-01"
)

#: Federal Reserve and BEA series, keyed by the file they are written to.
SERIES = {
    "DGS10": "10-year Treasury constant maturity, per cent, H.15",
    "DGS2": "2-year Treasury constant maturity, per cent, H.15",
    "T10Y2Y": "10-year minus 2-year, as the Federal Reserve publishes it, H.15",
    "DEXUSEU": "US dollars per euro, noon buying rate, H.10",
    "GDPC1": "Real gross domestic product, billions of chained 2017 dollars, BEA",
}


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "quashz-capture"})
    with urllib.request.urlopen(request, timeout=120) as response:
        if response.status != 200:
            raise SystemExit(f"{url} returned {response.status}")
        body: bytes = response.read()
    if not body.strip():
        raise SystemExit(f"{url} returned an empty body")
    return body


def rows_of(body: bytes) -> int:
    return len([line for line in body.decode("utf-8").splitlines()[1:] if line.strip()])


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    captured: list[dict[str, object]] = []

    for series, description in SERIES.items():
        body = fetch(FRED.format(series=series))
        header = body.decode("utf-8").splitlines()[0]
        # THE HOST THAT ANSWERS ANYWAY. fred.stlouisfed.org returns HTTP 200 for a request
        # carrying a vintage it will not honour, so a capture that trusted the status code
        # would record current values under any pretence. Nothing here asks for a vintage, and
        # the header is checked to be the bare series id so that a future edit adding one
        # cannot pass silently.
        if header != f"observation_date,{series}":
            raise SystemExit(f"{series} returned an unexpected header: {header!r}")
        (DATA / f"{series}.csv").write_bytes(body)
        captured.append(
            {
                "series": series,
                "description": description,
                "publisher": (
                    "Bureau of Economic Analysis" if series == "GDPC1" else "Federal Reserve"
                ),
                "via": "FRED graph CSV, keyless",
                "rows": rows_of(body),
                "sha256": hashlib.sha256(body).hexdigest(),
            }
        )
        print(f"  {series}: {rows_of(body)} rows")

    body = fetch(ECB)
    (DATA / "ECB_EXR_D_USD_EUR_SP00_A.csv").write_bytes(body)
    columns = len(body.decode("utf-8").splitlines()[0].split(","))
    captured.append(
        {
            "series": "EXR.D.USD.EUR.SP00.A",
            "description": "ECB reference exchange rate, US dollar per euro, 2.15pm CET",
            "publisher": "European Central Bank",
            "via": "ECB Data Portal SDMX CSV, keyless",
            "rows": rows_of(body),
            "columns_kept": columns,
            "sha256": hashlib.sha256(body).hexdigest(),
            "modification": (
                "None. The ECB permits reuse only without modification, including of the "
                f"metadata, so all {columns} columns are committed as served and every "
                "normalisation happens at read time."
            ),
        }
    )
    print(f"  ECB EXR: {rows_of(body)} rows, {columns} columns kept")

    source = {
        "captured": datetime.date.today().isoformat(),
        "licence": {
            "Federal Reserve and BEA": "United States government work, reproduced freely",
            "European Central Bank": (
                "Reuse permitted without modification only, metadata included, so the file is "
                "committed exactly as served"
            ),
        },
        "excluded_by_licence": (
            "The FRED-hosted S&P 500 and VIX series are excluded by name: they are redistributed "
            "on FRED under terms that do not permit republication, unlike the government series "
            "beside them."
        ),
        "series": captured,
    }
    (DATA / "SOURCE.json").write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {(DATA / 'SOURCE.json').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.URLError as exc:
        print(f"the capture could not reach a publisher: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
