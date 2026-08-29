"""Every committed measurement is produced by a script, and CI runs that script and compares it.

A repository whose subject is whether a number was knowable cannot itself carry numbers nobody
re-derives. What is asserted here is the join between three things that drift apart quietly: a
directory under docs/evidence, the script that writes it, and a CI step that runs the script AND
diffs the result.

THE WORKFLOW IS PARSED RATHER THAN GREPPED. Searching the whole file for a script's name passes
on a comment mentioning it, which is how a sibling ended up with an enforcement satisfied by
prose about a step that had been deleted. Only `run:` bodies are searched, minus their own
comment lines.
"""

from __future__ import annotations

import json
import pathlib
import re

import yaml

REPO = pathlib.Path(__file__).resolve().parents[1]
EVIDENCE = REPO / "docs" / "evidence"
WORKFLOWS = REPO / ".github" / "workflows"


def run_commands() -> str:
    executed: list[str] = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job in workflow["jobs"].values():
            for step in job.get("steps", []):
                command = step.get("run")
                if isinstance(command, str):
                    executed += [
                        line for line in command.splitlines() if not line.strip().startswith("#")
                    ]
    assert executed, "the workflows run no commands at all"
    return "\n".join(executed)


def evidence_directories() -> list[pathlib.Path]:
    if not EVIDENCE.exists():
        return []
    return sorted(path for path in EVIDENCE.iterdir() if path.is_dir())


def test_every_evidence_directory_has_a_summary_that_is_json() -> None:
    directories = evidence_directories()
    assert directories, "there is no committed evidence at all, so this checks nothing"
    for directory in directories:
        summary = directory / "summary.json"
        assert summary.exists(), f"{directory.name} has no summary.json for CI to diff"
        json.loads(summary.read_text(encoding="utf-8"))


def test_ci_runs_every_harness_and_diffs_the_whole_directory() -> None:
    """Running a harness proves it does not crash. Diffing what it wrote is the check."""
    executed = run_commands()
    for directory in evidence_directories():
        relative = f"docs/evidence/{directory.name}"
        assert f"git diff --exit-code -- {relative}\n" in executed, (
            f"CI does not diff {relative}, so a changed outcome is not a red build"
        )
        assert f'test -z "$(git status --porcelain {relative})"' in executed, (
            f"CI diffs {relative} and never checks for a file the harness newly created"
        )

    harnesses = sorted(
        [*(REPO / "scripts").glob("measure_*.py"), *(REPO / "scripts").glob("measure_*.sh")]
    )
    assert harnesses, "no measurement harness exists"
    for script in harnesses:
        assert f"scripts/{script.name}" in executed, f"CI never runs scripts/{script.name}"


def test_no_script_that_reaches_the_network_is_run_by_a_required_job() -> None:
    """The other direction, and it is just as important.

    A required job that depends on somebody else's availability goes red for reasons nobody here
    caused, and the response to that is to stop reading red builds. The scripts that reach live
    publishers belong to a manual workflow that is allowed to fail.

    ASKS WHAT THE SCRIPT IMPORTS, AND THE FIRST VERSION ASKED WHAT IT WAS CALLED. It matched
    `capture_*.py` and went red when `capture_evidence.py` arrived, which captures the demo's
    own stdout and reaches nothing at all. A rule keyed on a filename is a rule about a naming
    habit; this one is about the property that actually matters.
    """
    executed = run_commands()
    reaches_network = ("urllib.request", "import requests", "httpx", "urlopen")
    for script in sorted((REPO / "scripts").glob("*.py")):
        text = script.read_text(encoding="utf-8")
        if not any(marker in text for marker in reaches_network):
            continue
        assert f"scripts/{script.name}" not in executed, (
            f"scripts/{script.name} reaches a live publisher and a workflow runs it. Every "
            f"required job must run from the committed corpus"
        )


def test_no_workflow_carries_a_schedule() -> None:
    """A rule of this repository rather than an omission, so it is asserted rather than intended."""
    for path in sorted(WORKFLOWS.glob("*.yml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        triggers = workflow.get(True) or workflow.get("on") or {}
        assert "schedule" not in triggers, f"{path.name} carries a schedule"


def test_every_third_party_action_in_every_workflow_is_pinned_by_commit() -> None:
    """A tag is a pointer its owner can move, and every workflow file is read, not just one."""
    text = "\n".join(path.read_text(encoding="utf-8") for path in sorted(WORKFLOWS.glob("*.yml")))
    uses = re.findall(r"^\s*(?:- )?uses:\s*(\S+)\s*(#.*)?$", text, re.MULTILINE)
    assert uses, "the workflows have no `uses:` lines at all"
    for ref, trailing in uses:
        if ref.startswith("PNX89/"):
            continue
        assert re.search(r"@[0-9a-f]{40}$", ref), f"{ref} is pinned by a movable tag"
        assert trailing.strip().startswith("#"), f"{ref} is pinned with no version named beside it"
