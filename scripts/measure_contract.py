"""Run the vendor contract in both directions, and keep what a vendor would actually read.

    uv run --group verdict --group contract python scripts/measure_contract.py

WHY BOTH DIRECTIONS. A contract that has never been seen to fail is a contract nobody has
tested, and the commonest way for one to be useless is to be satisfiable by any file at all. So
this builds the admitted frame, verifies it, and then verifies a DELIBERATELY BROKEN copy of it,
and both outcomes are recorded. The broken copy is a copy: a harness that edits the real thing
to prove a point leaves the repository wrong when it is interrupted.

WHAT THE CONTRACT IS FOR, and why it is not the same as the admission predicate. The predicate
in `quashz.ledger` decides what may be trained on and lives in this repository. The contract is
the artefact handed TO the vendor: it is executed as SQL against the file where it sits, and its
output is a table their own engineer can argue with. An expectation suite buried inside a
scheduler cannot be handed to anybody.

SODA 4, NOT 3. The 3.x line that carries SodaCL is frozen at soda-core-duckdb 3.5.6, which pins
duckdb<1.1.0 and declares no requires_python at all. This repository reads DuckDB 1.5, so the
choice is not a preference.
"""

from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quashz import frame, ledger  # noqa: E402

TARGET = ROOT / "target"
OUT = ROOT / "docs" / "evidence" / "contract"
CONTRACT = ROOT / "contract" / "candidate_dataset.yml"
DATASOURCE = ROOT / "contract" / "datasource.yml"


def build_database(path: pathlib.Path, *, break_it: bool) -> int:
    """Write the candidate frame into a DuckDB file, optionally with a vendor's mistake in it."""
    path.unlink(missing_ok=True)
    connection = ledger.connect(path)
    admitted_rows, _ = frame.build()
    ledger.admit(connection, admitted_rows)
    connection.execute(
        """
        create or replace table candidate_frame as
        select decision_date, level, slope, fx, gdp, gdp_age_days, outcome from candidate
        """
    )
    if break_it:
        # ONE ROW DUPLICATED AND ONE VALUE REMOVED, which is what a vendor file actually looks
        # like when it is wrong: not corrupt, just quietly restated twice with a gap in it.
        connection.execute(
            "insert into candidate_frame select * from candidate_frame order by decision_date "
            "limit 1"
        )
        connection.execute(
            "update candidate_frame set slope = null where decision_date = "
            "(select max(decision_date) from candidate_frame)"
        )
    counted: int = connection.execute("select count(*) from candidate_frame").fetchone()[0]
    connection.close()
    return counted


def verify() -> tuple[int, str]:
    result = subprocess.run(
        [
            "uv",
            "run",
            "--group",
            "contract",
            "soda",
            "contract",
            "verify",
            "-c",
            str(CONTRACT.relative_to(ROOT)),
            "-ds",
            str(DATASOURCE.relative_to(ROOT)),
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    return result.returncode, result.stdout + result.stderr


def counts(output: str) -> dict[str, int]:
    """Pull the summary table out of what Soda printed, so the record is its numbers not mine."""
    found: dict[str, int] = {}
    for label in ("Checks", "Passed", "Failed", "Warned", "Not Evaluated"):
        match = re.search(rf"\|\s*{label}\s*\|\s*(\d+)", output)
        if match:
            found[label.lower().replace(" ", "_")] = int(match.group(1))
    return found


def main() -> int:
    TARGET.mkdir(exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    database = TARGET / "candidate.duckdb"

    honest_rows = build_database(database, break_it=False)
    honest_code, honest_output = verify()
    honest = counts(honest_output)

    shutil.copy(database, TARGET / "candidate_honest.duckdb")
    broken_rows = build_database(database, break_it=True)
    broken_code, broken_output = verify()
    broken = counts(broken_output)

    if honest_code != 0:
        print("the contract failed on the admitted frame, which it must not", file=sys.stderr)
        print(honest_output[-2000:], file=sys.stderr)
        return 1
    if broken_code == 0:
        print(
            "the contract PASSED a file carrying a duplicated key and a missing value, so it "
            "would accept anything and is not a contract",
            file=sys.stderr,
        )
        return 1
    if not honest.get("checks") or honest["checks"] != broken.get("checks"):
        print("the two runs executed different numbers of checks", file=sys.stderr)
        return 1

    summary = {
        "rows_in_the_admitted_frame": honest_rows,
        "rows_after_a_vendor_mistake": broken_rows,
        "checks_in_the_contract": honest["checks"],
        "on_the_admitted_frame": honest,
        "on_the_broken_copy": broken,
        "exit_code_when_honest": honest_code,
        "exit_code_when_broken": broken_code,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    def table(output: str) -> list[str]:
        lines = output.splitlines()
        start = next((i for i, line in enumerate(lines) if line.startswith("# Summary")), None)
        return lines[start : start + 10] if start is not None else []

    with (OUT / "both-directions.txt").open("w", encoding="utf-8") as handle:
        print("$ soda contract verify   # the admitted frame", file=handle)
        for line in table(honest_output):
            print(line, file=handle)
        print(file=handle)
        print(
            "$ soda contract verify   # the same frame with a vendor's mistake in it", file=handle
        )
        print("#   one decision date duplicated, one slope removed", file=handle)
        for line in table(broken_output):
            print(line, file=handle)
        print(file=handle)
        print(
            "This is the artefact handed to the vendor. Their engineer runs the same two "
            "commands against",
            file=handle,
        )
        print(
            "their own copy and gets the same table, which is what an argument about a data "
            "problem needs.",
            file=handle,
        )

    print((OUT / "both-directions.txt").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
