"""The vendor contract, checked offline against what running it recorded.

The claim being defended is not that the contract passes. It is that the contract has been
watched FAILING, on a file broken the way a vendor file is actually broken, and that it executes
the same number of checks in both directions so the failure is a verdict rather than a crash.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import yaml

REPO = pathlib.Path(__file__).resolve().parents[1]
EVIDENCE = REPO / "docs" / "evidence" / "contract"
CONTRACT = REPO / "contract" / "candidate_dataset.yml"
DATASOURCE = REPO / "contract" / "datasource.yml"


def summary() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((EVIDENCE / "summary.json").read_text(encoding="utf-8"))
    return loaded


def test_the_contract_has_been_seen_to_pass_and_to_fail() -> None:
    """Both directions, with the counts recorded rather than described."""
    numbers = summary()
    assert numbers["exit_code_when_honest"] == 0
    assert numbers["exit_code_when_broken"] != 0, (
        "the contract accepted a file with a duplicated key and a missing value, so it would "
        "accept anything"
    )
    assert numbers["on_the_admitted_frame"]["failed"] == 0
    assert numbers["on_the_broken_copy"]["failed"] >= 2, (
        "two mistakes were planted and fewer than two checks caught them"
    )


def test_the_same_checks_ran_in_both_directions() -> None:
    """Otherwise the failure could be the contract not running rather than the file being wrong."""
    numbers = summary()
    assert numbers["checks_in_the_contract"] >= 4
    assert (
        numbers["on_the_admitted_frame"]["checks"]
        == numbers["on_the_broken_copy"]["checks"]
        == numbers["checks_in_the_contract"]
    )
    assert numbers["on_the_broken_copy"].get("not_evaluated", 0) == 0, (
        "a check went unevaluated on the broken file, so part of the contract is untested there"
    )


def test_the_contract_is_a_file_a_vendor_could_be_handed() -> None:
    """It has to be readable, executable and free of this machine.

    A data source file carrying an absolute path from somebody's laptop is not an artefact
    anybody else can run, and that is what this file was for one commit.
    """
    contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    assert contract["dataset"]
    assert contract["description"].strip()
    assert contract["columns"], "a contract with no columns checks nothing"
    for column in contract["columns"]:
        assert column["name"] and column["checks"], f"{column} declares no check"

    source = DATASOURCE.read_text(encoding="utf-8")
    assert "/Users/" not in source and "/home/" not in source, (
        "the data source file carries an absolute path from the machine that wrote it"
    )
    assert "database:" in source, (
        "the DuckDB plugin infers the connection class from this key and raises on any other, "
        "so `path:` would fail with a message about the input rather than about the key"
    )


def test_the_transcript_shows_the_table_a_vendor_would_read() -> None:
    text = (EVIDENCE / "both-directions.txt").read_text(encoding="utf-8")
    assert "# Summary" in text
    assert "vendor's mistake" in text
    assert "| Failed" in text
